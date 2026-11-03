# SpreadsheetBench 2 / Financial Constraint Witness Oracle v1

这轮在原来的三维评分器上增加第四类**补充性数值证据**：不依赖公式完全同字串，而是把候选公式放入多组独立设定的财务前提数据中，验证它是否满足业务恒等式。

> **精确边界：这不是 Excel 或 LibreOffice 计算引擎，没有重新计算真实工作簿，也不能替代独立财务审计。** 新模块只支持经过审核的少量引用和算术语法。遇到不支持的公式返回 `unverified`，绝不能偷偷当作正确。

## 实现范围

- **8 类注入故障、32 个公式位置：** 情景选择、Cohort 首年、Synergized EBITDA、债务出资比例、Organic 收入组成、Organic EBITDA、合并收入来源、合并协同 EBITDA 来源。
- 每处公式使用 **5 组不同的模拟业务输入**，覆盖开关打开/关闭、情景 1/2/3，以及区分正确/错误引用的数值。
- 使用受限 Excel 公式解释器（数字、单元格引用、加减乘除、`SUM`、`CHOOSE`），不执行用户提供的 Python/Shell。
- 另外为 **LBO 退出总债务 Y20:AC20 五处**和**Valuation Bridge C7 一处**增加 6 个补充性财务数值约束。它们仅作为额外修改证据，不改变最终的严格最小修复 `pass`。
- 数学等价公式可通过相同数值约束。例如 `=E28-E31-E32` 与 `=E28-E33` 在 `E33=E31+E32` 条件下同样通过。

## 评分 JSON 新字段

`financial_constraints`：
- `rule_count`：本题注入故障的数值约束数量
- `pass` / `fail` / `unverified`：分别代表模拟验证通过、存在反例、或公式不在受限语法支持范围
- `rules[].counterexamples`：数值反例，帮助定位不满足的业务恒等式

`supplemental_business_evidence`：
- `evaluated_extra_cells`：与已编写业务约束匹配的额外修改数量
- `improved_under_synthetic_witnesses`：在模拟输入中从违反约束变为满足约束的修改数量
- `items[]`：每处具体修改及保守的风险说明

这两部分只增加诊断信息，保留 `injected_faults`、`extra_changes`、`artifact_integrity`、`verdict` 原字段和严格 `pass` 的语义。

## Windows PowerShell：离线回归（零模型 API 调用）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_financial_constraints.py scripts/spreadsheetbench2_oracle_v3.py scripts/spreadsheetbench2_fault_factory.py

python -m unittest discover -s tests -p "test_spreadsheetbench2_financial_constraints.py" -v
python -m unittest discover -s tests -p "test_spreadsheetbench2_oracle_v3.py" -v
```

本地有 `runs/ssb2-injected-01` 时，测试将对 56 道题进行正反样本数值验证。无本地数据时相应集成测试会跳过，不能视为通过。

对已完成的 GPT-0033 进行离线复评：

```powershell
python scripts/spreadsheetbench2_fault_factory.py grade `
  --out "runs/ssb2-injected-01" `
  --id "SSB2-MUT-0033" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --golden "runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx" `
  --summary-only `
  --report "runs/ssb2-fault-gpt-0033/oracle_v4_full.json"
```

**预期：** 严格 `pass=false`；注入修复 1/2；`financial_constraints.pass=1`、`fail=1`、`unverified=0`；45 项额外修改；其中 6 项通过独立的合成财务约束检查（5 项 LBO 退出总债务、1 项 Valuation Bridge）。它们具有额外业务证据，但不代表整个财务模型已经重算或审计合格。

## 下一步

应基于经过独立验证的业务规则，增加对 LBO 债务偿还、现金累积、退出估值等全链条的 Excel 兼容数值重算。尤其需要在多种财务输入/情景和循环引用设置下验证模型，避免仅靠公式形式或模拟输入制造虚假的正确性。
