# Excel ToolUse：中文批次格式 v1

现在按一个批次一个目录组织已生成的 Excel 故障题目。一个题目一个子目录，固定包含以下文件：

    runs/batches/SSB2-20261103-B01/
      batch_manifest.json
      SSB2-NEW-0001/
        prompt.md
        input.xlsx
        metadata.json
        private/
          answer.xlsx
          oracle.json
          validate.py
      SSB2-NEW-0002/
        ...
      batch_selftest.json

**prompt.md 为中文题面**，明确要求只恢复本题人为注入的公式错误、其余内容不变。每题的 input.xlsx 是错误工作簿；private/answer.xlsx 是出题前的规范化基线 Golden。private/oracle.json 保存注入事实和哈希，private/validate.py 是只依赖 Python 标准库的严格验证器。

**模型只能看到 prompt.md 和 input.xlsx**，其余答案/验证代码不得放进模型工具工作区。

## 把现有 136 道题整理为新批次

在项目根目录的 PowerShell：

    git fetch origin feature/dynamic-w6-pilot
    git merge FETCH_HEAD

    python scripts/spreadsheetbench2_batch_pack.py pack --source runs/ssb2-discovered-v2 --out runs/batches/SSB2-20261103-B01

    python scripts/spreadsheetbench2_batch_pack.py selftest --out runs/batches/SSB2-20261103-B01

    python -m unittest discover -s tests -p test_spreadsheetbench2_batch_pack.py -v

预期创建 136 份独立题目目录，正反测试 136/136 通过。上述命令均不调用模型 API，且不覆盖旧的 runs/ssb2-discovered-v2。

## 后续一键生成 + 打包

    python scripts/spreadsheetbench2_discovery_factory.py generate --dataset runs/ssb2-injected-01 --out runs/ssb2-discovered-next --compound 200 --seed 20261104 --batch-out runs/batches/SSB2-20261104-B01

生成器保留旧内部目录供历史工具使用，同时可选输出中文标准批次。更换批次名以避免覆盖。

## 查看单题与离线评分

    $case = "SSB2-NEW-0068"
    $batch = "runs/batches/SSB2-20261103-B01"
    Get-Content "$batch/$case/prompt.md" -Raw -Encoding UTF8

    python "$batch/$case/private/validate.py" --submission "模型输出路径/input.xlsx"

或使用统一批次入口：

    python scripts/spreadsheetbench2_batch_pack.py grade --out runs/batches/SSB2-20261103-B01 --case SSB2-NEW-0068 --submission "模型输出路径/input.xlsx"

## 当前评分规则及边界

评分器以已锁定 Golden 为准，检查注入目标公式是否恢复、非目标单元格是否意外修改，以及公式、数据、样式和可检查的 OOXML 结构。不会自动认为 GPT 自行额外修复的其他内容正确。输出必须符合标准答案才会通过。

这仍然是**受控错误恢复**任务，而不是要求修复整本财务模型的所有历史潜在错误。当前模型中的候选注入机制需要经过更多业务复核；所有变体仍来自同一份母工作簿，不可作为独立样本计算置信区间。
