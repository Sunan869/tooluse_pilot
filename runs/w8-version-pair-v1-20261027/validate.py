import sys,json,tempfile,os,shutil,hashlib
from pathlib import Path
from types import SimpleNamespace
from openai.types.chat import ChatCompletion
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.w8_task import Environment,specs
from tooluse_pilot.executable_runner import run_candidate
from independent_w7 import oracle
from w8_data import create
out=ROOT/'offline-validation';out.mkdir(exist_ok=False);summaries=[]
for seed in (20261027,20261028):
 for condition in ('static','dynamic'):
  suffix=condition+('-shuffle' if seed==20261028 else '');folder=ROOT/'candidates'/('case-'+suffix);case,data=create(folder,condition,seed)
  # Independent final-data oracle: no call to environment update or answer function.
  import copy
  final=copy.deepcopy(data)
  if condition=='dynamic':
   row=next(g for g in final['grades'] if g['student_id']=='s05' and g['batch_id']=='B2');row.update(record_id='g-B2-s05-r2',revision=2,score=96,supersedes='g-B2-s05-r1')
  gold=oracle(final)
  assert [x[0] for x in gold]==(['s05','s03','s01'] if condition=='dynamic' else ['s03','s01','s06'])
  with tempfile.TemporaryDirectory() as td:
   ref=Path(td)/'ref';shutil.copytree(folder,ref);e=Environment(case,ref);sequence=[]
   def call(name,args):sequence.append((name,args));return e.call(name,args)
   call('directory',{});call('read_rows',{'source':'enrollment','batch_id':'B2'});response=call('read_rows',{'source':'grades','batch_id':'B2'});status=call('get_status',{})
   if response['read_revision']!=status['current_revision']:call('read_rows',{'source':'grades','batch_id':'B2'})
   call('write_submission',{'expected_revision':status['current_revision'],'rows_json':json.dumps(gold)});call('read_submission',{});call('finish',{})
   assert e.score()['success'] and e.score()['actual']==gold
  class Client:
   def __init__(self):self.index=0;self.chat=SimpleNamespace(completions=self)
   def create(self,**kwargs):
    i=self.index;self.index+=1
    assert i<len(sequence),'Runner called model after successful terminal finish'
    calls=[{'id':'t'+str(i),'type':'function','function':{'name':sequence[i][0],'arguments':json.dumps(sequence[i][1])}}]
    if i==len(sequence)-1:calls.append({'id':'must-not-run','type':'function','function':{'name':'write_submission','arguments':json.dumps({'expected_revision':'R2','rows_json':'[]'})}})
    return ChatCompletion.model_validate({'id':'offline'+str(i),'object':'chat.completion','created':0,'model':'offline-reference','choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':calls}}]})
  runout=out/suffix;runout.mkdir();prev=Path.cwd();os.chdir(runout)
  try:r=run_candidate(folder/'candidate.json',ROOT/'gateway.flash.isolated.json','qwen',runout/'usage.sqlite',25,80,client_factory=Client)
  finally:os.chdir(prev)
  assert r['state']=='task_completed' and r['score']['success'] and r['tool_calls']==len(sequence) and r['invalid_tool_actions']==0
  (runout/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8');summaries.append({'case':suffix,'mock_requests':r['requests'],'tools':r['tool_calls'],'expected':gold,'score':r['score']})
# Explicit budget and no-tool termination: distinguish completion from a model stopping.
folder=ROOT/'candidates/case-static'
class Stopped:
 def __init__(self):self.chat=SimpleNamespace(completions=self)
 def create(self,**kwargs):return ChatCompletion.model_validate({'id':'offline-stop','object':'chat.completion','created':0,'model':'offline','choices':[{'index':0,'finish_reason':'stop','message':{'role':'assistant','content':'done'}}]})
for label,budget,client in [('budget',0,Stopped),('model-stop',1,Stopped)]:
 runout=out/label;runout.mkdir();prev=Path.cwd();os.chdir(runout)
 try:r=run_candidate(folder/'candidate.json',ROOT/'gateway.flash.isolated.json','qwen',runout/'usage.sqlite',budget,80,client_factory=client)
 finally:os.chdir(prev)
 assert not r['task_completed'] and not r['score']['success'];assert r['budget_exhausted']==(label=='budget')
 (runout/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8')
(out/'SUMMARY.json').write_text(json.dumps({'model_calls':0,'reference_pairs':summaries,'terminal_tests':'No model or queued tool after finish; budget and model-stop not completion'},ensure_ascii=False,indent=2),encoding='utf-8')
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and ('code' in p.parts or 'candidates' in p.parts or p.name in ('launch.py','EXPERIMENT-SPEC.txt','independent_w7.py'))}
(ROOT/'FROZEN-MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps({'reference_runs':4,'terminal_cases':2,'tools':[s['tools'] for s in summaries],'new_model_calls':0}))
