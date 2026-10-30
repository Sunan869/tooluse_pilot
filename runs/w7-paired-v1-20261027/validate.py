import sys,json,tempfile,os,hashlib,copy
from pathlib import Path
from types import SimpleNamespace
from openai.types.chat import ChatCompletion
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.w7_task import Environment,answer_rows,specs
from tooluse_pilot.executable_runner import run_candidate
from independent_w7 import oracle
from w7_data import create,dataset
out=ROOT/'offline-validation';out.mkdir(exist_ok=False)
results=[]
for seed in (20261027,20261028):
 for condition in ('clean','coverage','conflict'):
  suffix=condition+('-shuffle' if seed==20261028 else '')
  folder=ROOT/'candidates'/('case-'+suffix);case,data=create(folder,condition,seed)
  assert answer_rows(data)==oracle(data)
  with tempfile.TemporaryDirectory() as td:
   import shutil
   ref=Path(td)/'ref';shutil.copytree(folder,ref);env=Environment(case,ref);sequence=[]
   def call(n,a):
    sequence.append((n,a));return env.call(n,a)
   call('directory',{})
   for source in ('enrollment','grades'):
    args={'source':source}
    while True:
     r=call('read_rows',args)
     if not r['has_more']:break
     args={'source':source,'cursor':r['next_cursor']}
   call('write_submission',{'rows_json':json.dumps(oracle(data),ensure_ascii=False)});call('finish',{})
   assert env.score()['success'] and env.score()['coverage_complete'] and env.score()['evidence_valid']
  class Client:
   def __init__(self):self.index=0;self.chat=SimpleNamespace(completions=self)
   def create(self,**kwargs):
    i=self.index;self.index+=1
    msg={'role':'assistant','content':None,'tool_calls':[{'id':'t'+str(i),'type':'function','function':{'name':sequence[i][0],'arguments':json.dumps(sequence[i][1])}}]} if i<len(sequence) else {'role':'assistant','content':'Done'}
    return ChatCompletion.model_validate({'id':'offline'+str(i),'object':'chat.completion','created':0,'model':'offline-reference','choices':[{'index':0,'finish_reason':'tool_calls' if i<len(sequence) else 'stop','message':msg}]})
  runout=out/suffix;runout.mkdir();previous=Path.cwd();os.chdir(runout)
  try:r=run_candidate(folder/'candidate.json',ROOT/'gateway.flash.isolated.json','qwen',runout/'usage.sqlite',25,80,client_factory=Client)
  finally:os.chdir(previous)
  assert r['score']['success'] and r['invalid_tool_actions']==0
  (runout/'result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2),encoding='utf-8')
  results.append({'case':suffix,'requests_mock':r['requests'],'tools':r['tool_calls'],'score':r['score'],'dataset_sha256':hashlib.sha256((folder/'dataset.json').read_bytes()).hexdigest()})
assert len({r['dataset_sha256'] for r in results[:3]})==1
assert len({r['dataset_sha256'] for r in results[3:]})==1
# Boundary agreement over different orderings and validity/eligibility changes.
for seed in range(100):
 d=dataset(seed)
 for i,g in enumerate(d['grades']):
  if (i+seed)%7==0:g['published']=False
  if (i+seed)%11==0:g['valid']=False
  if (i+seed)%5==0:g['score']=0
 for i,e in enumerate(d['enrollment']):
  if (i+seed)%3==0:e['status']='inactive'
 assert answer_rows(d)==oracle(d)
(out/'SUMMARY.json').write_text(json.dumps({'model_calls':0,'boundary_cases':100,'runs':results},ensure_ascii=False,indent=2),encoding='utf-8')
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and ('code' in p.parts or 'candidates' in p.parts or p.name in ('launch.py','EXPERIMENT-SPEC.txt','independent_w7.py'))}
(ROOT/'FROZEN-MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print(json.dumps({'reference_runs':len(results),'boundary_cases':100,'tools':[r['tools'] for r in results],'new_model_calls':0}))
