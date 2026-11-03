import sys,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.reservation_task import Environment,calculate
from tooluse_pilot.real_w6_reconciliation import report
from independent_oracle import independent
folder=ROOT/'references/case-4';shutil.copytree(ROOT/'candidates/case-4',folder)
case=json.loads((folder/'candidate.json').read_text(encoding='utf-8'));env=Environment(case,folder)
expected=[['17084','6','H','4063'],['15449','7','B','2743'],['10067','5','B','2743']]
stages=[];checks=[];sheets=['Orders','Corrections','Policy','Priority','Limits','Dependencies','Commitments','Withdrawn','Stage']
for round in range(3):
 for sheet in sheets:env.call('read_sheet',{'sheet':sheet})
 answer,rows=independent(env.wb);assert (answer,rows)==calculate(env.wb);assert answer==expected[round],(round,answer)
 stages.append({'round':round,'summary':answer,'decisions':rows})
 if round<2:
  for tool in ['receive_update','finish']:
   try:env.call(tool,{});raise AssertionError('premature gate accepted')
   except ValueError:checks.append('reject '+tool+' round '+str(round))
 env.call('write_decisions',{'rows_json':json.dumps(rows)})
 for c,v in zip(['B2','B3','B4','B5'],answer):env.call('write_summary',{'cell':c,'value':v})
 env.call('write_report',{'text':report(answer)});env.call('save_workbook',{})
 if round<2:sheets=env.call('receive_update',{})['changed_sheets']
env.call('finish',{});score=env.score();assert score['success'] and len(env.calls)<=80
record={'stages':stages,'reference_calls':env.calls,'reference_tool_calls':len(env.calls),'reference_score':score,'checks':checks,'model_calls':0}
env.close();(folder/'reference-result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'stages':expected,'tools':record['reference_tool_calls'],'success':score['success']}))
