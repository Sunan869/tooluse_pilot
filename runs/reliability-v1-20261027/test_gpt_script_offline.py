import sys,os,json,importlib.util
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent;out=ROOT/'offline-gpt-script-test';out.mkdir(exist_ok=False)
config=out/'mock-config.json';config.write_text(json.dumps({'base_url_env':'OFFLINE_STUB_URL','models':{'gpt':{'model':'gpt-6-astra','api_type':'responses','api_key':'test-only-not-used'}}}),encoding='utf-8');os.environ['OFFLINE_STUB_URL']='http://offline.invalid/v1'
import openai
counter={'calls':0}
class Node:
 def __init__(self,n,a,i):self.type='function_call';self.name=n;self.arguments=a;self.call_id='mock'+str(i);self.id=self.call_id
 def model_dump(self,**kw):return dict(type=self.type,name=self.name,arguments=self.arguments,call_id=self.call_id,id=self.id)
class Response:
 def __init__(self,node):self.id='offline-response';self.output=[node];self.usage=None
 def model_dump(self,**kw):return {'id':self.id,'model':'offline-mock-not-a-model-call','output':[x.model_dump() for x in self.output]}
class Fake:
 def __init__(self,**kwargs):
  self.http=kwargs['http_client'];self.i=0;self.responses=self;self.events=[e for e in json.loads((ROOT/'reference'/Path.cwd().name/'result.json').read_text(encoding='utf-8'))['events'] if e['event']=='tool_call']
 def create(self,**kwargs):
  assert self.i<len(self.events);e=self.events[self.i];self.i+=1;counter['calls']+=1;return Response(Node(e['tool'],e['arguments'],self.i))
 def close(self):self.http.close()
openai.OpenAI=Fake
spec=importlib.util.spec_from_file_location('gpt_script',ROOT/'run_gpt_comparison.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
sys.argv=['run_gpt_comparison.py','--output-root',str(out/'comparison'),'--config',str(config),'--execute'];module.main();first=counter['calls'];module.main();assert counter['calls']==first
results=json.loads((out/'comparison/comparison-summary.json').read_text(encoding='utf-8'));assert len(results)==12 and all(r['score']['success'] for r in results)
(out/'TEST-RESULT.json').write_text(json.dumps({'real_model_calls':0,'mock_request_count':first,'cases':12,'passed':True,'resume_additional_calls':counter['calls']-first,'note':'OpenAI class replaced by in-process fake; offline.invalid was never contacted.'},indent=2),encoding='utf-8');print('OFFLINE GPT script: all12 pass; resume adds0 calls; real model calls0')
