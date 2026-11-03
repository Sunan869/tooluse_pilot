# SpreadsheetBench 2 · 五年期 LBO 债务／现金流／退出估值情景重放 v1

本模块为母文件 `01_01 / Double Counting_input.xlsx` 增加了 **可实际执行的 2026–2030 年 LBO 子模型重放**。它不同于前一轮“逐条公式做模拟算术”的验证：本轮沿用工作簿实际的 Q:U 债务计划公式，计算循环贷款、利息、现金、偿债及 Y:AC 退出回报，随后与**完全不读取 Excel 公式的独立资金台账**对照。

**科学边界：这不是完整 Excel 重算。** P&L 的自由现金流、SOFR、EBITDA、并购债务/权益、税率均由 9 组**明确声明的合成情景**注入。尚未重新计算 14 张工作表、Excel Data Tables、敏感性表或迭代计算的所有影响。输出只能作为子图数值证据，不能直接等同于工作簿全面审计通过。

## 计算范围

- 2026–2030：LBO!Q:U 的债务计划（含 Q54:Q92 相关公式）、循环贷款未使用额度费用和迭代收敛检查
- LBO!F17:F22：期初资金来源与资金用途平衡
- LBO!Y:AC：退出总债务、现金、股权价值、投资额、MOIC、IRR 公式
- 独立资金台账：债务期初/期末勾稽、现金流扣减、循环贷款优先偿还、强制摊还、提前偿还、流动性缺口、假设现金全额留存的退出现金余额

循环贷款未使用额度费用依赖期末贷款余额，而期末余额反过来依赖该费用，因此使用**固定点迭代**，单年度最多 100 次，记录是否收敛和残差。

## 9 组业务情景

| 场景 | 测试重点 |
|---|---|
| base | 正常自由现金流与贷款偿还 |
| mandatory_amort | 非零强制摊还 |
| ma_off | 关闭并购后债务及权益出资应受开关控制 |
| low_cash | 低现金流、循环贷款额度风险 |
| negative_cash | 负自由现金流和融资缺口 |
| zero_revolver | 不使用循环贷款 |
| high_fee | 较高未使用额度费及循环依赖收敛 |
| positive_sweep | 较高现金流和退出现金留存 |
| entry_revolver_funded | 期初循环贷款资金来源非零，检查 Sources & Uses |

## 评测语义

结果分为**两类**：

1. `hard_invariant_failures`：债务期初期末勾稽、强制摊还后的现金流、资金来源与用途平衡、分列现金时所用退出总债务等计算恒等式；
2. `policy_or_liquidity_alerts`：额度不足、潜在融资缺口、并购资金未跟随开关、退出现金是否跨年留存等风险/政策判断。**现金留存是一种显式假设，不可当作所有公司的唯一正确政策。**

`independent_ledger` 假定：利息以现金支付（不额外资本化 PIK）、循环贷款优先偿还、强制摊还先于提前偿还、盈余现金不分红而留存。**当实际模型政策不满足这些假设，差异应判为待复核，而非立即给模型扣分。**

模型提交缺少受支持的公式时，脚本应返回 `unverified_reason`，而非硬凑计算结果。新报告不会更改旧版 `pass` 或 1/2 注入修复率。

## 拉取和离线测试（不调用 GPT/Qwen API）

```powershell
git fetch origin feature/dynamic-w6-pilot
git merge FETCH_HEAD

python -m py_compile scripts/spreadsheetbench2_lbo_replay.py scripts/spreadsheetbench2_fault_factory.py scripts/spreadsheetbench2_run_fault.py

python -m unittest discover -s tests -p "test_spreadsheetbench2_lbo_replay.py" -v
```

对 GPT-0033 进行五年期复评，写出完整明细：

```powershell
python scripts/spreadsheetbench2_lbo_replay.py `
  --dataset "runs/ssb2-injected-01" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --report "runs/ssb2-fault-gpt-0033/lbo_replay_v1.json"
```

也可以从既有 Oracle 入口一次性输出全部诊断：

```powershell
python scripts/spreadsheetbench2_fault_factory.py grade `
  --out "runs/ssb2-injected-01" `
  --id "SSB2-MUT-0033" `
  --submission "runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx" `
  --golden "runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx" `
  --lbo-scenarios --summary-only `
  --report "runs/ssb2-fault-gpt-0033/oracle_with_lbo_v1.json"
```

上面所有命令均只读取本地文件；**不会调用任何模型 API**。新实验报告不会覆盖旧版 `oracle_v4_full.json`。

## 已用上传的真实母文件与 GPT 输出核验

在 9 组合成情景中，原始 LBO 公式有 **22 项**硬性勾稽差异，GPT 修改后是 **0 项**。原始模型共报告 **26 条**流动性或政策提示，GPT 修改后 **9 条**。45 个年度的循环贷款费用解都收敛。

典型发现：

- 非零强制摊还时，原 `Q80:U80` 遗漏强制摊还对剩余现金的扣减；GPT 的修改在子模型中通过。
- 并购开关为 0 时，原 `Q59:U59` 和 `Y25:AC25` 仍产生并购资金支出；GPT 修改后能随开关关闭。
- 期初循环贷款非零时，原 `F21/F22` 的资金来源口径出现差异；GPT 修改改善了资金平衡。
- 负现金流下，两份模型都可能突破 Revolver 额度，因此 GPT 并未修复所有财务风险。

这组数值**不能抵消**先前已确认的 `Ex 4 - Organic Operating Model!E40` 漏修。因此 GPT-0033 的注入题成绩仍是 **1/2**，严格 Oracle 仍不通过。

## 文件

- `scripts/spreadsheetbench2_lbo_replay.py`：受限公式 AST 求值、费用循环解、五年期债务计划、独立资金台账、CLI
- `tests/test_spreadsheetbench2_lbo_replay.py`：9 组情景、5 年度、额度风险及真实 GPT 文件离线回归
- `scripts/spreadsheetbench2_fault_factory.py`：可选 `--lbo-scenarios`，不改变旧评分器
- `scripts/spreadsheetbench2_run_fault.py`：未来模型测试结束后可选同一数值重放，不自动启用

后续如要向“官方可验收”的完整 LBO 计算推进，需要 Excel 兼容计算环境、全依赖图、实际情景输入追溯，以及现金保留/派息/再投资和循环贷款超额融资的业务政策批准。
