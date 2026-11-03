# SpreadsheetBench 2：业务机制发现与 XLSX 批量故障注入 v2

在已有 8 类注入机制基础上，新增 **18 类候选机制、88 个已核对原公式的注入位置**。通过跨业务工作表组合，再生成 **48 道复合故障任务**，共 **136 份不同的 XLSX 输入**。

这里的 136 是不同故障场景，并不是独立业务母文件的数量，也不代表 136 道已经难倒 GPT 的题。当前业务规则来自母文件公式和行标签，需要进一步抽样独立审查。

## 新机制

- PF P&L：合并收入、合并毛利、合并 EBITDA 的组成遗漏；毛利率与 EBITDA 利润率分母混淆（5 种）
- Organic：毛利用错成本、R&D/SG&A 费用汇总遗漏、服务收入拆分错误（3 种）
- M&A：收购对价按收入而非 EBITDA 计价、目标公司毛利/EBITDA 利润率错用、权益对价用错债务比例、并购毛利率分母错用（5 种）
- LBO：定期贷款余额滚动漏偿债、总利息漏 Revolver、循环贷款期末余额遗漏支取或偿还、收入增长率与利润率混淆、EBITDA 预测用错毛利率（5 种）

每个候选注入点必须匹配源工作簿实际公式，并在 5 组确定性数值输入中产生至少一个可复核的计算反例。**这些数值反例只是证明原公式与注入公式行为不同，不独立证明原始公式的全部业务正确性。**

复合任务每道包含 2～4 种不同机制，至少跨两张业务工作表；输入 XLSX 使用 OOXML 定位替换，仅允许受影响的工作表 XML 部件发生变化。题面不透露错误机制、位置或数量；答案和母文件只保留在 `private/`。

## 一次拉取 + 生成 + 评分自测（Windows PowerShell，**零模型 API 调用**）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD
python -m py_compile scripts/spreadsheetbench2_discovery_factory.py

python scripts/spreadsheetbench2_discovery_factory.py generate `
  --dataset "runs/ssb2-injected-01" `
  --out "runs/ssb2-discovered-v2" `
  --compound 48

python scripts/spreadsheetbench2_discovery_factory.py selftest `
  --out "runs/ssb2-discovered-v2"

python -m unittest discover -s tests -p "test_spreadsheetbench2_discovery_factory.py" -v
```

生成器使用已有的规范化母工作簿，**不会修改原始 Excel**，如果输出目录存在则直接拒绝覆盖。

预期输出：`generated=136`、`mechanisms=18`、`unique_workbooks=136`，以及自测全部通过。实际结果以你 Windows 上运行的日志为准。

## 输出与评分

```text
runs/ssb2-discovered-v2/
  manifest.json
  public/tasks.jsonl
  private/normalized_baseline.xlsx
  private/oracle.json
  private/witnesses.json
  cases/SSB2-NEW-0001/input/Double Counting_mutated.xlsx
  cases/SSB2-NEW-0001/instruction.md
  cases/SSB2-NEW-0001/output/
  ...
  selftest_report.json
```

`public/tasks.jsonl` 和各题目录 `input/`、`instruction.md` 可给模型使用；**绝对不能向模型提供 private/、witnesses.json 或自测 fixtures**。

单题离线评分：

```powershell
python scripts/spreadsheetbench2_discovery_factory.py grade `
  --out "runs/ssb2-discovered-v2" `
  --id "SSB2-NEW-0089" `
  --submission "MODEL_OUTPUT.xlsx"
```

本轮继续使用严格的目标公式复原与非目标单元格保护规则。为新机制建立的纯数值见证仅作区分性证据，不能替代 Excel 兼容的完整情景重算，也尚未接入 GPT/Qwen 自动批测入口。

## 本轮重点与后续优先级

这轮回归到了**新增独立故障机制与真正不同的输入 XLSX**。后续应选取每类机制的代表性题目，优先用本地 Qwen 做失败模式采样，再对不同机制中少量高难候选测试 GPT，建立难度排序；无需为全部 136 道题立刻付费调用 API。
