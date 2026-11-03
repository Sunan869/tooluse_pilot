# SpreadsheetBench 2 / 01_01：复杂 XLSX 批量出题原型

本模块已提交至 `feature/dynamic-w6-pilot`。它使用用户现有的真实 `Double Counting_input.xlsx` 和 `01_golden.xlsx`，校验 SHA-256，**不覆盖原始工作簿**。

## 运行（PowerShell）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_factory.py

python scripts/spreadsheetbench2_factory.py generate `
  --source "runs/ssb2-debugging-baseline/01_Debugging_01_01/input/Double Counting_input.xlsx" `
  --golden "runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx" `
  --out "runs/ssb2-family-01"

python scripts/spreadsheetbench2_factory.py selftest `
  --source "runs/ssb2-debugging-baseline/01_Debugging_01_01/input/Double Counting_input.xlsx" `
  --out "runs/ssb2-family-01"
```

如果已经生成了目标 `--out` 目录，请换一个全新的目录名；生成器会拒绝覆盖，避免破坏已有实验记录。

## 题目构成

| 题型 | 候选数 | 验证方法 |
|---|---:|---|
| XLSX 修复（repair_xlsx） | 7 | 目标公式、非目标值/公式变化及工作表清单 |
| 错误定位（localize） | 7 | 单元格集合 |
| 公式推导（propose_formula） | 7 | 公式字符串规范化 |
| 输入依赖（identify_inputs） | 7 | 六个 Cohort 输入单元格 |
| 直接跨表依赖（direct_dependency） | 4 | 显式单元格引用静态检查 |
| 反事实算术（counterfactual_check） | 4 | 独立给定数值求和 |
| 财务业务推理（business_reasoning） | 2 | 仅人工审查 |

总计 38 道 **研究候选**，其中 36 道可使用当前规则自动评分，另 2 道需要业务专家复核。

## 输出目录

```text
runs/ssb2-family-01/
  manifest.json
  public/tasks.jsonl
  private/oracle.json
  private/source_evidence.json
  private/SSB2-01_01-xxx.json
  fixtures/
  selftest_report.json
```

`public/tasks.jsonl` 是给被测模型的题面；运行时应按任务 ID 从中选题，并**单独装载原始 XLSX**。不得把 `private/`、`fixtures/`、可信评分器源码或 Golden 文件挂给模型。Git 中只保存生成器和说明文档，所有派生输出由本地生成并由现有 `/runs/**` 忽略规则隔离。

## 评分示例

```powershell
python scripts/spreadsheetbench2_factory.py grade `
  --source "runs/ssb2-debugging-baseline/01_Debugging_01_01/input/Double Counting_input.xlsx" `
  --out "runs/ssb2-family-01" `
  --id "SSB2-01_01-001" `
  --submission "PATH_TO_MODEL_OUTPUT.xlsx"
```

## 科学有效性限制

- 38 是**任务变体数量**，不是 38 个独立难题。它们共享同一母文件、同一组错误机制，评分统计必须按母文件分组。
- 当前 XLSX Oracle 只检查目标公式、非目标单元格的公式/值、Sheet 列表与定义名称；不执行 Excel 数值重算，也不证明所有特殊 OOXML 部件/格式不变。
- Golden 中的特殊 Excel Data Table 公式和大面积样式转换不能当作已确认错误。
- 直接跨表依赖目前只解析显式单格引用，不能冒充完整依赖图。
- 财务业务推理题的参考信息只是审查证据，不能自动当作唯一正确结论。
- 自测通过只证明正负样本能被当前规则区分，不代表官方 SpreadsheetBench 评分已通过。

下一阶段应该围绕真正不同的业务错误机制做独立审计和计算校验，而不是简单增加同一公式的语言改写。
