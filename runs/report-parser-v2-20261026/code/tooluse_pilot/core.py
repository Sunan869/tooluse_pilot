"""Business semantics; uses integer cents for exact comparisons."""
from collections import defaultdict

def compute(sheets):
    suppliers={str(r['supplier_id']):r for r in sheets['Suppliers']}
    rules={str(r['dept']):int(r['approval_limit_cents']) for r in sheets['Rules']}
    by_order=defaultdict(list)
    for p in sheets['Payments']: by_order[str(p['order_id'])].append(p)
    result=[]
    for order in sheets['Orders']:
        if order['status']!='ACTIVE' or order['test_flag']==1: continue
        order_id=str(order['order_id']); sid=str(order['supplier_id']); dept=str(order['dept'])
        gross=int(order['amount_cents'])
        records=by_order[order_id]
        paid=sum(int(p['amount_cents']) for p in records if p['kind']=='PAYMENT')
        refunds=sum(int(p['amount_cents']) for p in records if p['kind']=='REFUND')
        net=paid-refunds
        errors=[]
        if sid not in suppliers or suppliers[sid]['enabled'] != 1: errors.append('SUPPLIER_INVALID')
        if dept not in rules: errors.append('RULE_MISSING')
        elif gross>rules[dept]: errors.append('REQUIRES_APPROVAL')
        if net != gross: errors.append('PAYMENT_MISMATCH')
        if errors:
            result.append({'order_id':order_id,'expected_cents':gross,'net_paid_cents':net,'issues':'|'.join(sorted(errors))})
    return sorted(result,key=lambda r:r['order_id'])
