# 采购异常核验任务

读取 input/procurement.xlsx 中 Orders、Payments、Suppliers、Rules 四个工作表。
对 status=ACTIVE 且 test_flag=0 的订单逐条核验：
1. 供应商必须在 Suppliers 中且 enabled=1，否则标记 SUPPLIER_INVALID；
2. 订单金额超过所属部门 approval_limit_cents 时标记 REQUIRES_APPROVAL；部门规则缺失标记 RULE_MISSING；
3. 同一订单的 PAYMENT 金额合计减去 REFUND 金额合计，若不等于订单 amount_cents，标记 PAYMENT_MISMATCH。

输出 output/anomalies.csv，CSV 列顺序为 order_id,expected_cents,net_paid_cents,issues。只输出存在异常的订单，issues 使用字典序排序后以 | 分隔，按 order_id 升序排列。金额单位全部为整数分。不要修改输入文件。
