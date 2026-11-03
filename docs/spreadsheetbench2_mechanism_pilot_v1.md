# 136 道候选题：按机制分层抽样与批量模型验证

核心目标已从“继续生成更多文件”转为**评测不同错误机制是否真的能挑战模型**。生成数据、Oracle 自测都完成后，应在至少四个业务模块中抽样，先低成本本地 Qwen，再用同样的题目对照 GPT。不要把共享母文件的多个样本统计成独立观察。

新增脚本：`scripts/spreadsheetbench2_mechanism_pilot.py`

## 1. 只选题（离线，无 API）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_mechanism_pilot.py
python -m unittest discover -s tests -p "test_spreadsheetbench2_mechanism_pilot.py" -v

python scripts/spreadsheetbench2_mechanism_pilot.py plan `
  --dataset "runs/ssb2-discovered-v2" `
  --plan "runs/ssb2-pilot-plan-01.json" `
  --singles 6 --compounds 2
```

计划生成 8 道：6 道单点、2 道跨表组合，优先覆盖 LBO / PF P&L / Organic / M&A 四个工作表和不同机制；选择是固定的、可重复的。计划文件仅存样本 ID、机制标签、输入 SHA 和来源分组，不存标准答案。**不会执行模型调用**。

## 2. 本地 Qwen 小规模运行（明确调用 API）

前提：本地 Qwen 的 OpenAI 兼容端口已启动，Docker 沙盒镜像已准备好。命令使用你之前的模型设置；请不要把私有 Token 粘贴到聊天中。

```powershell
$env:MODEL_BASE_URL = "http://10.10.23.7:5610/v1"
$env:MODEL_ID = "Qwen3.8-Flash-Next-AWQ-INT4"
$env:MODEL_API_KEY = "not-needed"

python -u scripts/spreadsheetbench2_mechanism_pilot.py run `
  --plan "runs/ssb2-pilot-plan-01.json" `
  --out "runs/ssb2-pilot-qwen-01" `
  --api-type chat_completions `
  --max-cases 2 --max-requests 25 --max-tools 60 `
  --execute
```

只有最后一条含 `run --execute` 的命令会调用模型 API。默认最多运行 2 道，避免不知情的大量调用；`--max-cases` 显式调整数量。结果保存到每个样本文件夹中的 `trusted_result.json` 及批次 `summary.json`，调用轨迹单独保存在 `runs/<run_id>.json`。

脚本仅复制对应 `input/` 和 `instruction.md` 到模型工具沙盒，**不会复制 `private/`、Oracle 或 normalized baseline**。评分由宿主机使用既有严格最小修复 Oracle 执行。

## 3. 汇总已有模型结果（离线）

```powershell
python scripts/spreadsheetbench2_mechanism_pilot.py report --out "runs/ssb2-pilot-qwen-01"
```

分别统计正常结束、预算耗尽、是否产出 XLSX，以及严格评分通过率。对于未交付文件的题不能推断其公式理解水平。Qwen 与 GPT 对照必须使用完全一致的 plan、输入、预算和工具能力。

## 研究限制

- 18 类是候选规则，原公式匹配和数值差异不足以完全证明业务正确；
- 136 道题属于同一母 XLSX，错误机制之间有依赖和重叠；
- 当前严格 Oracle 可能拒绝其他合理业务修复，因此“不通过”须结合日志分析；
- 一次模型失败不代表具有稳定难度，应在代表性机制上做重复试验；
- 先选题、少量验证、归因，再扩充机制，而不是直接批量消耗 GPT Token。
