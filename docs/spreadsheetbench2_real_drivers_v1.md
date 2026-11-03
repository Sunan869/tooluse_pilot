# SpreadsheetBench 2 — Real workbook driver bridge (01_01)

本模块在原有 LBO 五年期债务／现金流重放器之上，新增一个**真实工作簿驱动数据提取层**。不调用 GPT/Qwen，不修改任何 XLSX。

## 为什么要有这一层

前一版 LBO Replay 的 FCF、EBITDA、SOFR 和并购出资来自人工构造的 9 组反事实数字，适合验证现金流恒等式，但不能宣称接入了真实财务模型。

新文件 `scripts/spreadsheetbench2_real_drivers.py` 从原始 Excel XML 读取指定财务公式并沿依赖链计算：

- LBO!Q38:U38：2026–2030 自由现金流，受 PF P&L、Organic 与 M&A 影响
- LBO!Q23:U23：预测 EBITDA，并验证与 PF P&L C27:G27 一致
- M&A!C80:G80 / C81:G81：债务与权益并购出资
- LBO!Q52:U52：由 SOFR 月度预测 C8:C67 经实际公式求年均利率
- LBO!C41/C42/C43/C47/C49/C52、F17/F18/F19/F20/F28、C20：借款限制、利率、融资来源和退出倍数

支持受限语法：基本算术、百分比、SUM、AVERAGE、CHOOSE、INDEX/MATCH 精确匹配、IF、MIN、MAX 和跨表引用。其余公式会标为 `unverified`，不会被编造为成功。

注意：LBO!C36 使用历史单值数组公式，代码只对**精确匹配的原有数组公式**做标量化处理，并在 `warnings` 明确记录。因为原模型 LBO!P89 为空，期初现金按 0 假设，也明确标记。**这不是 Excel 全工作簿公式重算。**

## 两种不可混淆的比较

1. `submission_common_drivers`：基线和 GPT 使用完全相同的真实提取驱动数据，单独检验债务、现金及退出估值公式差异。
2. `submission_own_drivers`：分别从基线和 GPT 输出读取实际公式并计算驱动数据，允许 GPT 的上游修改传导到现金流与 EBITDA。

第二种方式能发现上游计算的差别，但仍是限定的财务子图计算，不是完整的 Excel 计算引擎。

## 拉取并测试（Windows PowerShell，零模型 API 调用）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_real_drivers.py
python -m unittest discover -s tests -p "test_spreadsheetbench2_real_drivers.py" -v
```

测试包括受限公式解释器拒绝危险表达式和循环依赖、实际控制开关、默认工作簿来源追踪、模型上游修改传导、18 个真实驱动情景。

## 运行完整 18 情景矩阵

```powershell
python scripts/spreadsheetbench2_real_drivers.py `
  --baseline "runs/ssb2-injected-01/private/normalized_baseline.xlsx" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --mode matrix `
  --out "runs/ssb2-fault-gpt-0033/real_drivers_matrix_v1.json"
```

输出简短汇总，完整驱动输入、每个情景的反例、来源警告写入 JSON，不会覆盖已有 `lbo_replay_v1.json`。

如果只需复核原母文件**实际的默认开关**：经营 Case=1、M&A Case=3、M&A 开关=1，可以执行：

```powershell
python scripts/spreadsheetbench2_real_drivers.py `
  --baseline "runs/ssb2-injected-01/private/normalized_baseline.xlsx" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --mode one --operating-case 1 --ma-case 3 --ma-switch 1 `
  --out "runs/ssb2-fault-gpt-0033/real_drivers_default_v1.json"
```

**基于已经上传的确切两份文件的本地结果：** 默认 2026 年 FCF 约 591.3684 百万美元、预测 EBITDA 约 780.2528 百万美元、SOFR 约 3.3183%；默认 M&A Case=3 下并购债务出资为 0。提取时追溯到 629 个相关单元格。

18 个情景（3×3×2）在受限计算器中都得到计算值：基线硬性勾稽差异 5 项；使用共同驱动数据的 GPT 输出 0 项；使用 GPT 自己计算的驱动数据时仍为 0 项。12 个情景中 GPT 上游修改改变 FCF/EBITDA 等驱动输入。**这不改变 GPT-0033 注入题漏修 E40 的事实，也不能据此宣称模型完整财务审计通过。**

## 科学边界

- 本模块仅覆盖可追踪的财务子图，特殊 Excel Data Table、完整迭代计算、外部数据查询、条件格式和宏等没有重算。
- 本文件是模拟财务模型的历史快照，SOFR、收入等单元格来自工作簿而非实时行情。
- 默认 P89 历史现金为空，期初现金 0 是显式假设，期初净债务从融资组合初始化；债务现金政策尚未得到权威确认。
- 所有 18 个情景是**同一母文件的组合控制测试**，不是 18 个独立 Benchmark 数据点。
- 这些结果只能作为补充数值证据，不能替换 Oracle 既有的注入修复率、人工业务复核和 Excel 文件保护评分。
