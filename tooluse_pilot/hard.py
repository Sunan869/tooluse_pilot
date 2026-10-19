"""Hard procurement reconciliation: independent seeded source data and authoritative oracle."""
import csv, json, random
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from openpyxl import Workbook
from .xlsx import read_sheets

ASOF=date(2026,9,30)
COLS={
 'Orders':['order_id','supplier_id','dept','amount_cents','status','test_flag','order_date'],
 'Payments':['payment_id','order_id','kind','amount_cents','posted_date','reversal_of'],
 'Suppliers':['supplier_id','enabled','effective_from','effective_to'],
 'Rules':['dept','approval_limit_cents','effective_from','effective_to','version'],
 'Amendments':['amendment_id','order_id','new_amount_cents','effective_from','approved'],
 'Aliases':['alias','canonical_supplier_id'],
 'Holds':['order_id','hold_from','hold_until','type'],
 'Notes':['code','description']
}
def active(day,begin,end):return begin<=day and (not end or day<=end)
def oracle(data):
    supplier_alias={r['alias']:r['canonical_supplier_id'] for r in data['Aliases']}
    supplier=defaultdict(list)
    for r in data['Suppliers']:supplier[r['supplier_id']].append(r)
    rules=defaultdict(list)
    for r in data['Rules']:rules[r['dept']].append(r)
    amendments=defaultdict(list)
    for r in data['Amendments']:amendments[r['order_id']].append(r)
    holds=defaultdict(list)
    for r in data['Holds']:holds[r['order_id']].append(r)
    pays=defaultdict(list)
    for p in data['Payments']:pays[p['order_id']].append(p)
    result=[]
    for order in data['Orders']:
        if order['status']!='ACTIVE' or int(order['test_flag']):continue
        oid=order['order_id'];day=order['order_date']; amount=int(order['amount_cents']);issues=[]
        valid_amends=[r for r in amendments[oid] if int(r['approved'])==1 and r['effective_from']<=ASOF.isoformat()]
        if valid_amends:
            chosen=sorted(valid_amends,key=lambda r:(r['effective_from'],r['amendment_id']))[-1];amount=int(chosen['new_amount_cents'])
        sid=supplier_alias.get(order['supplier_id'],order['supplier_id'])
        suppliers=[r for r in supplier[sid] if active(day,r['effective_from'],r['effective_to'])]
        if len(suppliers)!=1 or int(suppliers[0]['enabled'])!=1:issues.append('SUPPLIER_INVALID')
        dept_rules=[r for r in rules[order['dept']] if active(day,r['effective_from'],r['effective_to'])]
        if len(dept_rules)!=1:issues.append('RULE_MISSING')
        elif amount>int(dept_rules[0]['approval_limit_cents']):issues.append('REQUIRES_APPROVAL')
        if any(active(ASOF.isoformat(),h['hold_from'],h['hold_until']) for h in holds[oid]):issues.append('ON_HOLD')
        # Reversals are signed compensating ledger entries, not an additional refund.
        total=0
        for p in pays[oid]:
            if p['posted_date']>ASOF.isoformat():continue
            if p['kind']=='PAYMENT': sign=1
            elif p['kind']=='REFUND': sign=-1
            elif p['kind']=='REVERSAL':
                original=next((x for x in pays[oid] if x['payment_id']==p['reversal_of']),None)
                if original is None or original['kind'] not in ('PAYMENT','REFUND'): raise ValueError('invalid reversal reference')
                sign=-1 if original['kind']=='PAYMENT' else 1
            else: raise ValueError('unknown payment kind')
            total+=sign*int(p['amount_cents'])
        if total!=amount:issues.append('PAYMENT_MISMATCH')
        if issues:result.append({'order_id':oid,'expected_cents':amount,'net_paid_cents':total,'issues':'|'.join(sorted(issues))})
    return sorted(result,key=lambda x:x['order_id'])

def make_hard_case(root,seed=20261019,count=180):
    root=Path(root);(root/'input').mkdir(parents=True,exist_ok=True);(root/'private').mkdir(parents=True,exist_ok=True)
    rng=random.Random(seed)
    data={name:[] for name in COLS}
    for i in range(1,14):
        sid=f'S{i:03d}'
        data['Suppliers'] += [dict(supplier_id=sid,enabled=1,effective_from='2025-01-01',effective_to='2026-06-30'),dict(supplier_id=sid,enabled=int(i%6!=0),effective_from='2026-07-01',effective_to='')]
        data['Aliases'].append({'alias':f'OLD-{sid}','canonical_supplier_id':sid})
    for dept in ['ENG','OPS','FIN','SALES']:
        for v,start,end,limit in [(1,'2025-01-01','2026-03-31',1250000),(2,'2026-04-01','2026-07-31',850000),(3,'2026-08-01','',1700000)]:
            data['Rules'].append(dict(dept=dept,approval_limit_cents=limit+(300000 if dept=='FIN' else 0),effective_from=start,effective_to=end,version=v))
    data['Notes']=[{'code':'SNAPSHOT','description':'Snapshot is 2026-09-30; ignore payments posted after this date'}, {'code':'NEGATIVE','description':'PAYMENT adds money, REFUND subtracts money; REVERSAL offsets its referenced record with opposite sign'}, {'code':'DATES','description':'Approval rule and supplier registry effective on ORDER DATE; amendment approved effective on/before snapshot'}, {'code':'STATUS','description':'Only ACTIVE production orders; active hold is an exception'}]
    counter=0
    for i in range(count):
        oid=f'PO-{i+1:05d}'; amount=rng.randint(30000,2700000); day=date(2026,rng.randint(1,9),rng.randint(1,25)).isoformat()
        sid=f'S{rng.randint(1,13):03d}'; alias=f'OLD-{sid}' if i%7==0 else sid
        data['Orders'].append(dict(order_id=oid,supplier_id=alias,dept=rng.choice(['ENG','OPS','FIN','SALES']),amount_cents=amount,status='CANCELLED' if i%17==0 else 'ACTIVE',test_flag=int(i%19==0),order_date=day))
        if i%6==0:
            data['Amendments'].append(dict(amendment_id=f'A-{i:04d}',order_id=oid,new_amount_cents=amount+12000,effective_from='2026-08-15',approved=1))
            if i%12==0:data['Amendments'].append(dict(amendment_id=f'A2-{i:04d}',order_id=oid,new_amount_cents=amount+100000,effective_from='2026-10-02',approved=1))
        if i%9==0:data['Holds'].append(dict(order_id=oid,hold_from='2026-09-01',hold_until='2026-10-10',type='COMPLIANCE'))
        base=amount+(12000 if i%6==0 else 0)
        if i%11==0:base-=900
        counter+=1;pid=f'PAY-{counter:05d}'
        data['Payments'].append(dict(payment_id=pid,order_id=oid,kind='PAYMENT',amount_cents=base,posted_date='2026-09-10',reversal_of=''))
        if i%5==0:
            counter+=1;ref=f'PAY-{counter:05d}'
            data['Payments'].append(dict(payment_id=ref,order_id=oid,kind='REFUND',amount_cents=3000,posted_date='2026-09-11',reversal_of=''))
            if i%10==0:
                counter+=1
                # reversing a REFUND adds the same amount back
                data['Payments'].append(dict(payment_id=f'PAY-{counter:05d}',order_id=oid,kind='REVERSAL',amount_cents=3000,posted_date='2026-09-12',reversal_of=ref))
        if i%13==0:
            counter+=1;data['Payments'].append(dict(payment_id=f'PAY-{counter:05d}',order_id=oid,kind='PAYMENT',amount_cents=10000,posted_date='2026-10-05',reversal_of=''))
    # The independent oracle treats REVERSAL as positive when reversing a refund.
    # It will also reject a malformed reversal relation rather than silently using it.
    wb=Workbook();wb.remove(wb.active)
    for sheet_name,headers in COLS.items():
        ws=wb.create_sheet(sheet_name);ws.append(headers)
        for r in data[sheet_name]:ws.append([r.get(h,'') for h in headers])
        ws.freeze_panes='A2';ws.auto_filter.ref=ws.dimensions
    wb.save(root/'input'/'procurement.xlsx')
    answer=oracle(data)
    (root/'private'/'oracle.json').write_text(json.dumps({'schema_version':'1.0','rows':answer},ensure_ascii=False,indent=2),encoding='utf-8')
    (root/'private'/'generator_config.json').write_text(json.dumps({'seed':seed,'count':count,'family':'procurement_temporal_audit'},indent=2),encoding='utf-8')
    instructions='''# 集团采购核销和异常审计（2026年9月30日快照）\n\n读取 input/procurement.xlsx 所有相关工作表并产出 output/anomalies.csv。不要修改原文件。仅审计 ACTIVE 且 test_flag=0 的采购订单。\n\n业务规则：\n1. 供应商可能通过 Aliases 的历史 ID 关联到 Suppliers 的 canonical ID；供应商有效性必须依据订单日期选择生效区间，未找到或多条同时有效均视为 SUPPLIER_INVALID。\n2. 审批 Rules 按订单日期的生效区间选版本；缺失或重叠匹配标 RULE_MISSING；存在唯一规则且实际订单金额大于审批额度标 REQUIRES_APPROVAL。\n3. 已批准的 Amendments 按 snapshot 2026-09-30 之前已生效的最新一条修改订单金额；相同日期按 amendment_id 排序选最后一条。\n4. 截至 snapshot 的 Payments 中，PAYMENT 加、REFUND 减、REVERSAL 抵消 reversal_of 指定记录的原效果。只按 posted_date<=snapshot 统计。净支付不等于调整后的订单金额标 PAYMENT_MISMATCH。\n5. Holds 以 snapshot 日期判断是否生效，生效标 ON_HOLD。\n6. 每个异常订单只输出一行，包含所有命中的问题，不输出正常、测试或已取消订单。\n\n最终输出 output/anomalies.csv，列顺序严格为 order_id,expected_cents,net_paid_cents,issues；金额单位整数分，issues 的标签按字典序用 | 拼接，结果按 order_id 升序。不允许猜测或跳过未读取的工作表。\n'''
    (root/'instruction.md').write_text(instructions,encoding='utf-8')
    (root/'task.json').write_text(json.dumps({'schema_version':'1.0','task_id':'TOOL-XLSX-HARD-W07-W12-001','title':'集团采购历史版本核销审计','primary_weakness':'W12','secondary_weaknesses':['W7','W4','W11'],'allowed_modes':['structured','python_shell'],'input_files':['input/procurement.xlsx'],'output_file':'output/anomalies.csv','oracle_path':'private/oracle.json','tool_names':['list_sheets','read_rows','write_csv'],'grading':{'result_weight':0.85,'process_weight':0.15}},ensure_ascii=False,indent=2),encoding='utf-8')
    return root

def reference_hard(root):
    from .tools import StructuredTools
    tools=StructuredTools(root); all_rows={}
    for sheet in tools.list_sheets():
        rows=[];offset=0
        while True:
            batch=tools.read_rows(sheet,offset,100);rows+=batch
            if len(batch)<100:break
            offset+=100
        all_rows[sheet]=rows
    result=oracle(all_rows)
    tools.write_csv(result)
    root=Path(root)
    (root/'trace.json').write_text(json.dumps({'mode':'structured','calls':tools.calls},ensure_ascii=False,indent=2),encoding='utf-8')
    return root/'trace.json'
