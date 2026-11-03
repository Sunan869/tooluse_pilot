# SpreadsheetBench 2 01_01：业务约束驱动的故障注入 v1

本模块不再把同一组 16 个错误公式拆成多个措辞题。它基于已读取的真实工作簿，从 M&A、Organic Operating Model、PF P&L 三张业务表中，**选择源文件中已确认的公式**，在生成的独立工作簿里注入可回滚的错误。

## 当前实验范围

- 先以原始文件建立“规范化基线”，只修复已核查的 16 个 M&A 重复累计公式。这个基线不是已证明所有 14 张工作表完全正确的标准模型。
- 8 种注入机制 × 4 个具体公式位置 = 32 道单点故障。
- 另外通过固定种子抽取 24 道 2–4 种机制组合故障，总计 **56 份互不相同的 XLSX 输入文件**。
- 涉及：情景选择器、Cohort 首年错位、协同 EBITDA、债务与权益出资比例、Organic 收入组成、Organic EBITDA 桥接、PF 收入跨表误引、PF 协同 EBITDA 跨表误引。
- 题面不泄露工作表、错误位置、具体错误类型或正确答案；每份输入对应私有注入记录。
- 生成器使用 ZIP/OOXML 局部修改，未触及的 ZIP 部件字节不变。自测测试：标准基线应通过；原始注入文件、额外乱改、组合题只修一部分都应失败。
- **仅是 56 个受控故障场景，不是 56 个独立来源的高难 Benchmark。** 目前缺少 Excel 兼容计算引擎的独立数值验算及完整 OOXML 验证。

## PowerShell：离线生成和测试（**不调用 API**）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_factory.py scripts/spreadsheetbench2_fault_factory.py scripts/spreadsheetbench2_run_fault.py

python scripts/spreadsheetbench2_fault_factory.py generate `
  --source "runs/ssb2-debugging-baseline/01_Debugging_01_01/input/Double Counting_input.xlsx" `
  --golden "runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx" `
  --out "runs/ssb2-injected-01"

python scripts/spreadsheetbench2_fault_factory.py selftest `
  --out "runs/ssb2-injected-01"
```

目录 `--out` 不得预先存在。改种子使用 `--seed`，调整组合题数使用 `--compound`；生成器拒绝覆盖现有实验。

## 文件结构

```text
runs/ssb2-injected-01/
  manifest.json
  public/tasks.jsonl
  private/normalized_baseline.xlsx
  private/oracle.json
  cases/SSB2-MUT-0001/
    instruction.md
    input/Double Counting_mutated.xlsx
    output/
  ...
  selftest_report.json
```

**绝对不能向模型暴露** `private/`、`normalized_baseline.xlsx`、`oracle.json`。模型只能访问其题目的 input/、output/ 和 instruction.md。

## 单题评分（纯本地，不调用 API）

```powershell
python scripts/spreadsheetbench2_fault_factory.py grade `
  --out "runs/ssb2-injected-01" `
  --id "SSB2-MUT-0001" `
  --submission "PATH_TO_MODEL_OUTPUT.xlsx"
```

## 可选的实际模型调用（**会调用 API**）

使用配置好的 `MODEL_BASE_URL` / `MODEL_ID` / `MODEL_API_KEY`。例如 GPT Responses：

```powershell
python -u scripts/spreadsheetbench2_run_fault.py `
  --dataset "runs/ssb2-injected-01" `
  --id "SSB2-MUT-0033" `
  --out "runs/ssb2-fault-gpt-0033" `
  --api-type responses --max-requests 25 --max-tools 60
```

Qwen Chat Completions 使用 `--api-type chat_completions` 并改为本地 Qwen 的 URL/模型环境变量。运行器会创建隔离的单题工作区，**不将私有 Oracle 复制进去**，执行结束后在可信主机上评分并输出 `trusted_result.json`。

请先跑通离线测试，再决定是否调用付费模型。

## 结果解释和剩余风险

- 当前 Oracle 比较目标公式与全部非目标单元格的公式/值，检查 Sheet 列表、定义名称和 ZIP 部件集合；这是 **严格的最小修复条件**，可能拒绝业务上合理的其他修复或数学等价公式。
- 使用 openpyxl 等工具重新保存时，一些特殊 Excel 部件可能被重写或移除。出现 `zip_package_parts_changed` 应单独诊断为文件保护问题，不能直接称为业务推理失败。
- 未经过独立 Excel 重算；一些注入案例在默认场景下可能没有数值影响，但其引用/业务规则仍发生偏离。
- 这批题需要按母工作簿和注入机制分组评测，不能把 56 道视作 56 个独立统计样本。下一阶段应扩充真正独立的业务规则和独立的计算验收，不靠增加组合数宣称难度提升。
