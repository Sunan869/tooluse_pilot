# SpreadsheetBench 2 / 01_01：三维 Oracle v3

本版本对 **注入故障修复、额外修改的业务证据和 XLSX 结构完整性** 独立评分，不再把所有不在注入集合内的修改都解释为“业务错误”。

## 评分口径

| 输出字段 | 含义 | 自动化边界 |
|---|---|---|
| `injected_faults` | 本题已知注入公式中正确恢复的数量、漏修、非参考公式提案 | 对预设参考公式做严格检查；其他等价方案标为待审核 |
| `extra_changes` | 其他单元格改动明细和证据等级 | 可匹配 Golden 或已有审计证据；**不能自动认定业务正确** |
| `artifact_integrity` | ZIP 部件、关系、Sheet、定义名称、样式、合并区域、特殊公式及保护设置等 | 只检查指定的 OOXML 语义不变量，不是完整 Excel/OOXML 验证 |
| `verdict` | 分开陈述严格最小修复是否通过、已知故障是否全部修复、开放式审计是否待复核 | `pass` 保持旧版**严格最小修改**口径，方便回归对比 |

如果提供经过可信主机校验的 `--golden`，评分器能识别与 Golden 一致或在**纯单元格加法**上等价的额外修复；标签为 `golden_correlated`，并非完整业务核验。没有 Golden 或人工审计证据时，这些额外修改默认 `unreviewed`。

如果提供 `--review-evidence`（单独保存的业务审计 JSON），验证器会先核对注入输入、规范化基线和提交文件三个 SHA-256，再逐单元格核对审计标注与提交公式，最后标记 `plausible_unverified` / `business_policy_pending`。**标注文件不能来自被测模型的可读工作区，也不能直接代替独立专家审查。**

## 已有 GPT-0033 的离线复评（不调用模型 API）

在项目根目录的 PowerShell 执行：

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_fault_factory.py scripts/spreadsheetbench2_run_fault.py scripts/spreadsheetbench2_oracle_v3.py

python scripts/spreadsheetbench2_fault_factory.py grade `
  --out "runs/ssb2-injected-01" `
  --id "SSB2-MUT-0033" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --golden "runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx" `
  --summary-only `
  --report "runs/ssb2-fault-gpt-0033/oracle_v3_full.json"
```

预期结果：`injected_faults.fixed=1`、`total=2`、`recall=0.5`、`extra_changes.count=45`、`golden_correlated=5`，`artifact_integrity.preservation_pass=true`，仍然 `pass=false`。

如果您另外有之前的 `GPT0033_公式变更逐项审计.json`，可以在命令追加：

```powershell
  --review-evidence "本地实际保存路径/GPT0033_公式变更逐项审计.json"
```

文件必须与同一份 GPT 输出 SHA-256 对应，才会得到剩余 **28 项 `plausible_unverified`、12 项 `business_policy_pending`**。未提供时剩余 40 项保持 `unreviewed`，不应自行猜测。

## 56 道候选题的回归测试（不调用 API）

```powershell
python -m unittest discover -s tests -p "test_spreadsheetbench2_oracle_v3.py" -v
```

测试包含 56 个正反样本组合、GPT-0033 真实结果的条件回归、样式被改坏、特殊 Excel Data Table 公式损坏，以及受限的加法公式等价。没有 `runs/ssb2-injected-01` 数据目录时会跳过 XLSX 集成测试；并不代表 XLSX 测试已经通过。

## 后续真实模型运行

`scripts/spreadsheetbench2_run_fault.py` 现已默认使用三维 Oracle。可选 `--golden` 和 `--review-evidence` 参数仅在模型结束后，由可信主机评分，不会挂载到模型的 Docker 工作区。**这个命令会调用模型 API；上面的 `grade` 和 `unittest` 都不会。**

## 科学与工程限制

- 规范化基线不是经过独立审计证明的“整本工作簿唯一正确解”。`golden_correlated` 只是与官方 Golden 对应。
- 结构检查并未运行 Excel/LibreOffice，也没有重算数值、验证循环依赖或解释所有特殊扩展部件；改变 `calcOnSave` 等标志只作为警告。
- 对开放式审计的额外合理修改，最终仍需要按业务约束与情景重算审核。不得把 `minimal_repair_strict_pass=false` 等同于“所有额外修改错误”。
- 所有 56 道题仍来自同一个母 XLSX，统计上必须按母文件/故障机制分组。
