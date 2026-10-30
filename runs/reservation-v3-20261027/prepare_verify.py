import sys,json,shutil,hashlib
from pathlib import Path
from openpyxl import load_workbook
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.reservation_task import Environment,calculate
from tooluse_pilot.real_w6_reconciliation import report
from independent_oracle import independent

def main():
    source=ROOT.parent/'allocation-diamond-v2-20261026/candidates/case-2';folder=ROOT/'candidates/case-3';shutil.copytree(source,folder)
    case=json.loads((folder/'candidate.json').read_text(encoding='utf-8'))
    w=load_workbook(folder/'reconciliation.xlsx')
    for row in [['O',101,18,1,1,'active','Blue'],['P',113,15,1,1,'active','Red'],['Q',127,12,1,1,'active','Green']]:w['Orders'].append(row)
    for row in [['O',130],['P',125],['Q',120]]:w['Priority'].append(row)
    for s,rows in {'Commitments':[['ID','Amount']],'Withdrawn':[['ID']],'Stage':[['Key','Value'],['Current',0]]}.items():
        sh=w.create_sheet(s)
        for row in rows:sh.append(row)
    w.save(folder/'reconciliation.xlsx');w.close()
    case.update(id='reservation-v3-3',family='real_reservation',variant=3,updates=[
    {'withdraw':['D'],'tables':{'Policy':{'Cities':'Shenzhen','Budget':18000},'Corrections':{'A':23,'C':16,'E':15,'H':17,'K':17},'Limits':{'Red':7800,'Blue':11000,'Green':6700},'Priority':{'H':220,'F':215,'E':210,'I':205}}},
    {'withdraw':['E'],'tables':{'Policy':{'Budget':18500},'Corrections':{'A':30,'B':20,'C':20,'F':22,'N':14,'O':19,'P':14,'Q':13},'Limits':{'Blue':12000},'Priority':{'O':210,'P':205,'Q':200}}}])
    case.pop('revision',None)
    case['task']='''Complete THREE rounds (Stage Current 0, 1, 2) of reservation allocation. There are TWO receive_update calls, after delivering rounds 0 and 1; finish only after delivering round 2. Read all input sheets. IDs and dependency edges are unique; dependencies are acyclic and AND. All prices/quantities/amounts are integers. Corrections replace quantity by ID, otherwise Orders Qty applies. Normal amount = Price times corrected quantity.
At each round start, Commitments contains the previous delivered selected IDs and their LOCKED amounts (empty in round 0). Withdrawn lists explicit permanent cancellations. Remove withdrawn commitments, then repeatedly remove any remaining commitment with a prerequisite absent from the remaining commitments, until stable. Surviving commitments are RETAINED: keep their locked amounts even when quantity, price, cities, status, priority or per-order limits change. They reserve group capacity and total budget BEFORE processing any other order, and satisfy dependencies immediately, regardless of priority. Inputs guarantee surviving commitments fit current group and total limits. Do not double-count retained orders. Removed dependent commitments are released, not permanently withdrawn; process them as ordinary candidates at their current normal amount. Explicitly withdrawn IDs cannot re-enter.
Visit ALL orders exactly once, descending Priority Rank then ascending ID. A surviving commitment gets selected=1 and reason retained. Otherwise apply the FIRST matching reason: explicit Withdrawn -> cancelled; non-active status -> inactive; missing any Policy Cities -> city; normal amount strictly above Max per order -> per_order; any prerequisite not already selected (including retained) -> dependency; adding amount strictly exceeds its group Limits Capacity -> group_cap; adding amount strictly exceeds Policy Budget -> budget; otherwise select with reason selected and consume capacity. Equality is allowed. Rejected orders consume nothing and are never reconsidered in that round. This is greedy, not global optimization.
Write Decisions in processing order, exactly one [ID, amount, selected 0/1, reason] row per order. Amount is locked only for retained orders, normal for all others including cancelled. Summary B2:B5 = total selected amount, selected count, selected ID with highest amount (ties ascending ID), highest amount; empty selection = 0,0,NONE,0. Report must have explicit Total, Count, Winner, Amount fields. Save Decisions, Summary, report and workbook for every round before receive_update. Each update commits the saved selected IDs/amounts into Commitments and changes the announced sheets, with cumulative Withdrawn; read the changed sheets and apply the reservation procedure again. Updates do NOT clear capacity to zero or reprice retained commitments. After round 2 save the complete delivery and finish.'''
    (folder/'candidate.json').write_text(json.dumps(case,indent=2),encoding='utf-8')
    ref=ROOT/'references/case-3';shutil.copytree(folder,ref);env=Environment(case,ref);stages=[];checks=[]
    expected=[['18858','7','G','3006'],['17084','6','H','4063'],['15449','7','B','2743']]
    sheets=['Orders','Corrections','Policy','Priority','Limits','Dependencies','Commitments','Withdrawn','Stage']
    for round in range(3):
        if round<2:
            try:env.call('receive_update',{});raise AssertionError('stale outputs accepted')
            except ValueError:checks.append('stale output rejected round '+str(round))
            try:env.call('finish',{});raise AssertionError('early finish accepted')
            except ValueError:checks.append('early finish rejected round '+str(round))
        for sheet in sheets:env.call('read_sheet',{'sheet':sheet})
        answer,rows=independent(env.wb);assert (answer,rows)==calculate(env.wb);assert answer==expected[round],(round,answer)
        stages.append({'round':round,'summary':answer,'decisions':rows})
        env.call('write_decisions',{'rows_json':json.dumps(rows)})
        for c,v in zip(['B2','B3','B4','B5'],answer):env.call('write_summary',{'cell':c,'value':v})
        env.call('write_report',{'text':report(answer)});env.call('save_workbook',{})
        if round<2:sheets=env.call('receive_update',{})['changed_sheets']
    env.call('finish',{});score=env.score();assert score['success'];assert len(env.calls)<=80
    calls=list(env.calls);env.close()
    # Boundary and semantic comparisons use memory only, never model inputs.
    w=load_workbook(folder/'reconciliation.xlsx')
    for budget in [0,2603,18857,18858,19800,100000]:
        w['Policy']['B4']=budget;assert independent(w)==calculate(w)
    w.close()
    w=load_workbook(ref/'reconciliation.xlsx')
    for cell,value in [('B4','A'),('B2','0')]:
        original=w['Summary'][cell].value;w['Summary'][cell]=value;w.save(ref/'mutation.xlsx');w['Summary'][cell]=original
    w.close()
    record={'model_calls':0,'stages':stages,'reference_score':score,'reference_tool_calls':len(calls),'reference_calls':calls,'checks':checks,'boundary_comparisons':6}
    (ref/'reference-result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps({'reference_tool_calls':len(calls),'expected':expected,'checks':checks,'success':score['success']},indent=2))

if __name__=='__main__':main()
