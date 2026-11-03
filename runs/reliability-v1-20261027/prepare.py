import sys,json,tempfile,shutil,os,hashlib
from pathlib import Path
from types import SimpleNamespace
from openai.types.chat import ChatCompletion
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
import w7_data,w8_data,w9_data
from independent_w7 import oracle as sql_oracle
from independent_graph import oracle as graph_oracle
from tooluse_pilot.w7_task import Environment as E7
from tooluse_pilot.w8_task import Environment as E8
from tooluse_pilot.w9_task import Environment as E9
from tooluse_pilot.executable_runner import run_candidate
cases=[];refs=[];reference=ROOT/'reference';reference.mkdir(exist_ok=False)
for seed in (20261030,20261031):
 for cond in ('clean','coverage','conflict'):cases.append((f'w7-{seed}-{cond}',7,cond,seed))
for seed in (20261030,20261031):
 for cond in ('static','dynamic'):cases.append((f'w8-{seed}-{cond}',8,cond,seed))
for cond in ('transient','permanent'):cases.append((f'w9-fixed-{cond}',9,cond,None))
for name,fam,cond,seed in cases:
 folder=ROOT/'candidates'/('case-'+name)
 if fam==7:
  case,data=w7_data.create(folder,cond,seed);case['task']+=' finish 是最终不可撤销结束，runner 将立即停止，不再调用模型或执行排队工具；请在此之前检查和修正提交。';(folder/'candidate.json').write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8')
 elif fam==8:case,data=w8_data.create(folder,cond,seed)
 else:case,data=w9_data.create(folder,cond,True)
 with tempfile.TemporaryDirectory() as td:
  workspace=Path(td)/'ref';shutil.copytree(folder,workspace);env={7:E7,8:E8,9:E9}[fam](case,workspace);seq=[]
  def call(n,a):seq.append((n,a));return env.call(n,a)
  if fam in (7,8):
   call('directory',{})
   for source in ('enrollment','grades'):
    args={'source':source,'batch_id':'B2'}
    while True:
     response=call('read_rows',args)
     if not response['has_more']:break
     args={'source':source,'batch_id':'B2','cursor':response['next_cursor']}
   if fam==8:
    status=call('get_status',{})
    if response['read_revision']!=status['current_revision']:call('read_rows',{'source':'grades','batch_id':'B2'})
   # Oracle derives final snapshot independently from immutable input and declared treatment.
   import copy
   final=copy.deepcopy(data)
   if fam==8 and cond=='dynamic':
    row=next(g for g in final['grades'] if g['student_id']=='s05' and g['batch_id']=='B2');row.update(record_id='g-B2-s05-r2',revision=2,score=96,supersedes='g-B2-s05-r1')
   gold=sql_oracle(final);args={'rows_json':json.dumps(gold)}
   if fam==8:args['expected_revision']=status['current_revision']
   call('write_submission',args)
   if fam==8:call('read_submission',{})
  else:
   gold=graph_oracle(data,cond);call('get_package',{});call('list_routes',{'origin':data['start']});call('send_leg',{'route_id':data['fault_route']});call('inspect_incident',{'incident_id':'I001'})
   if cond=='permanent':
    for hub in data['hubs']:
     if hub not in (data['start'],data['destination']):call('list_routes',{'origin':hub})
   for route in gold['optimal_paths'][0]['path']:call('send_leg',{'route_id':route})
   call('get_package',{});call('get_ledger',{})
  call('finish',{});assert env.score()['success']
 class Client:
  def __init__(self):self.index=0;self.chat=SimpleNamespace(completions=self)
  def create(self,**kwargs):
   i=self.index;self.index+=1;assert i<len(seq),'Unexpected post-finish request'
   return ChatCompletion.model_validate({'id':'ref'+str(i),'object':'chat.completion','created':0,'model':'offline-reference','choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{'id':'t'+str(i),'type':'function','function':{'name':seq[i][0],'arguments':json.dumps(seq[i][1])}}]}}]})
 out=reference/name;out.mkdir();prev=Path.cwd();os.chdir(out)
 try:r=run_candidate(folder/'candidate.json',ROOT/'gateway.flash.isolated.json','qwen',out/'usage.sqlite',25,80,client_factory=Client)
 finally:os.chdir(prev)
 assert r['score']['success'] and r['state']=='task_completed' and r['invalid_tool_actions']==0
 (out/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');refs.append({'case':name,'family':fam,'condition':cond,'seed':seed,'gold':gold,'tools':r['tool_calls']})
plan={'version':1,'max_requests_per_run':25,'max_tools_per_run':80,'hard_total_api_limit':900,'cases':refs,'runs':[{'case':name,'repeat':rep,'output':f'case-{name}-attempt-{rep}'} for rep in (1,2,3) for name,*_ in cases]}
(ROOT/'MANIFEST.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'cases':len(refs),'planned_runs':len(plan['runs']),'reference_tools':[r['tools'] for r in refs],'real_model_calls':0}))
