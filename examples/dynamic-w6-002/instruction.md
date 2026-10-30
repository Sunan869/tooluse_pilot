# 集团采购核销和异常审计（2026年9月30日快照）

读取 input/procurement.xlsx 所有相关工作表并产出 output/anomalies.csv。不要修改原文件。仅审计 ACTIVE 且 test_flag=0 的采购订单。

业务规则：
1. 供应商可能通过 Aliases 的历史 ID 关联到 Suppliers 的 canonical ID；供应商有效性必须依据订单日期选择生效区间，未找到或多条同时有效均视为 SUPPLIER_INVALID。
2. 审批 Rules 按订单日期的生效区间选版本；缺失或重叠匹配标 RULE_MISSING；存在唯一规则且实际订单金额大于审批额度标 REQUIRES_APPROVAL。
3. 已批准的 Amendments 按 snapshot 2026-09-30 之前已生效的最新一条修改订单金额；相同日期按 amendment_id 排序选最后一条。
4. 截至 snapshot 的 Payments 中，PAYMENT 加、REFUND 减、REVERSAL 抵消 reversal_of 指定记录的原效果。只按 posted_date<=snapshot 统计。净支付不等于调整后的订单金额标 PAYMENT_MISMATCH。
5. Holds 以 snapshot 日期判断是否生效，生效标 ON_HOLD。
6. 每个异常订单只输出一行，包含所有命中的问题，不输出正常、测试或已取消订单。

最终输出 output/anomalies.csv，列顺序严格为 order_id,expected_cents,net_paid_cents,issues；金额单位整数分，issues 的标签按字典序用 | 拼接，结果按 order_id 升序。不允许猜测或跳过未读取的工作表。
