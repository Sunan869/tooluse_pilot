import sys,json,tempfile,os,shutil,hashlib,copy
from pathlib import Path
from types import SimpleNamespace
from openai.types.chat import ChatCompletion
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.w9_task import Environment,minimum_cost
from tooluse_pilot.executable_runner import run_candidate
from independent_graph import oracle
from w9_data import create
out=ROOT/'offline-validation';out.mkdir(exist_ok=False);summaries=[]
for renamed in (False,True):
 for condition in ('transient','permanent'):
  suffix=condition+('-renamed' if renamed else '');folder=ROOT/'candidates'/('case-'+suffix);case,data=create(folder,condition,renamed);gold=oracle(data,condition);assert minimum_cost(data,condition)==gold['minimum_cost']
  for pathindex,solution in enumerate(gold['optimal_paths']):
   with tempfile.TemporaryDirectory() as td:
    ref=Path(td)/'ref';shutil.copytree(folder,ref);e=Environment(case,ref);sequence=[]
    def call(name,args):sequence.append((name,args));return e.call(name,args)
    call('get_package',{});call('list_routes',{'origin':data['start']});failed=call('send_leg',{'route_id':data['fault_route']});assert failed['code']=='E503';call('inspect_incident',{'incident_id':'I001'})
    if condition=='permanent':
     for hub in data['hubs']:
      if hub not in (data['start'],data['destination']):call('list_routes',{'origin':hub})
    for route in solution['path']:assert call('send_leg',{'route_id':route})['success']
    call('get_package',{});call('get_ledger',{});call('finish',{});assert e.score()['success']
   class Client:
    def __init__(self):self.index=0;self.chat=SimpleNamespace(completions=self)
    def create(self,**kwargs):
     i=self.index;self.index+=1;assert i<len(sequence),'Unexpected model call after terminal'
     return ChatCompletion.model_validate({'id':'offline'+str(i),'object':'chat.completion','created':0,'model':'offline-reference','choices':[{'index':0,'finish_reason':'tool_calls','message':{'role':'assistant','content':None,'tool_calls':[{'id':'t'+str(i),'type':'function','function':{'name':sequence[i][0],'arguments':json.dumps(sequence[i][1])}}]}}]})
   runout=out/(suffix+'-path'+str(pathindex));runout.mkdir();prev=Path.cwd();os.chdir(runout)
   try:r=run_candidate(folder/'candidate.json',ROOT/'gateway.flash.isolated.json','qwen',runout/'usage.sqlite',25,80,client_factory=Client)
   finally:os.chdir(prev)
   assert r['state']=='task_completed' and r['score']['success'] and r['invalid_tool_actions']==0 and r['score']['actual_cost']==gold['minimum_cost']
   (runout/'result.json').write_text(json.dumps(r,indent=2),encoding='utf-8');summaries.append({'case':suffix,'path':solution['path'],'tools':r['tool_calls'],'mock_requests':r['requests'],'score':r['score']})
# Independent exhaustive enumeration agrees under timetable/cost boundary variations.
for departure in (660,719,720,721,840):
 for cost in (0,1,3,4):
  d=copy.deepcopy(data)
  for route in d['routes']:
   if route['route_id']==('r68' if renamed else 'a2'):route.update(departure=departure,arrival=max(780,departure+60),cost=cost)
  for c in ('transient','permanent'):assert minimum_cost(d,c)==oracle(d,c)['minimum_cost']
(out/'SUMMARY.json').write_text(json.dumps({'new_model_calls':0,'full_reference_runs':summaries,'boundary_oracle_comparisons':40},indent=2),encoding='utf-8')
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and ('code' in p.parts or 'candidates' in p.parts or p.name in ('launch.py','EXPERIMENT-SPEC.txt','independent_graph.py'))}
(ROOT/'FROZEN-MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps({'reference_runs':len(summaries),'tools':[s['tools'] for s in summaries],'boundary_comparisons':40,'model_calls':0}))
