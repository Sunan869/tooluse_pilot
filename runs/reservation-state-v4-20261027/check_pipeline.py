import os,sys,json,shutil
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.reservation_task import Environment
from tooluse_pilot import executable_runner
from tooluse_pilot.real_w6_reconciliation import report
from openai.types.chat import ChatCompletion
case=json.loads((ROOT/'candidates/case-4/candidate.json').read_text(encoding='utf-8'))
ref=json.loads((ROOT/'references/case-4/reference-result.json').read_text(encoding='utf-8'))
folder=ROOT/'mutation-check-v2';shutil.copytree(ROOT/'candidates/case-4',folder);env=Environment(case,folder)
for call in ref['reference_calls']:env.call(call['tool'],call['args'])
assert env.score()['success'];checks=[]
for cell,value in [('B2','0'),('B3','1'),('B4','A'),('B5','4110')]:
 old=env.wb['Summary'][cell].value;env.wb['Summary'][cell]=value;env.wb.save(env.path);assert not env.score()['checks']['result'];env.wb['Summary'][cell]=old;checks.append('wrong summary '+cell)
env.wb.save(env.path)
old=env.wb['Decisions']['B2'].value;env.wb['Decisions']['B2']=old+1;env.wb.save(env.path);assert not env.score()['checks']['decisions'];env.wb['Decisions']['B2']=old;env.wb.save(env.path);checks.append('wrong decision amount')
p=folder/'report.txt';text=p.read_text(encoding='utf-8');p.write_text(text+'\nWinner: A\n',encoding='utf-8');assert not env.score()['checks']['report'];p.write_text(text,encoding='utf-8');checks.append('conflicting report')
assert env.score()['success'];env.close()
groups=[];pending=[]
for c in ref['reference_calls']:
 if pending and pending[-1]['tool']=='read_sheet' and c['tool']!='read_sheet':
  groups.append(pending);pending=[]
 pending.append(c)
 if c['tool'] in ['save_workbook','receive_update','finish']:
  # Separate read responses from writes so the scripted schedule respects information dependencies.
  groups.append(pending);pending=[]
assert not pending
class Fake:
 def __init__(self):self.chat=SimpleNamespace(completions=self);self.i=0
 def create(self,**kwargs):
  chunk=groups[self.i] if self.i<len(groups) else [];self.i+=1
  return ChatCompletion.model_validate({'id':'offline-'+str(self.i),'created':0,'model':'offline-scripted','object':'chat.completion','choices':[{'index':0,'finish_reason':'tool_calls' if chunk else 'stop','message':{'role':'assistant','content':None if chunk else 'done','tool_calls':[{'id':'c'+str(self.i)+'-'+str(j),'type':'function','function':{'name':c['tool'],'arguments':json.dumps(c['args'])}} for j,c in enumerate(chunk)]}}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}})
out=ROOT/'offline-pipeline-v2';out.mkdir(exist_ok=False);os.chdir(out)
result=executable_runner.run_candidate(ROOT/'candidates/case-4/candidate.json',ROOT/'gateway.flash.isolated.json','qwen',out/'usage.sqlite',25,80,client_factory=Fake)
assert result['score']['success'];assert result['tool_calls']==46
(ROOT/'PIPELINE-VALIDATION-v2.json').write_text(json.dumps({'new_model_calls':0,'mock_responses':result['requests'],'tool_calls':result['tool_calls'],'score':result['score'],'rejected_mutations':checks},indent=2),encoding='utf-8')
print(json.dumps({'new_model_calls':0,'mock_responses':result['requests'],'tool_calls':result['tool_calls'],'rejected_mutations':checks,'success':result['score']['success']}))
