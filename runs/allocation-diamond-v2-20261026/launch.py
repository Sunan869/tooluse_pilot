import sys,os,json,datetime
from pathlib import Path
root=Path(__file__).resolve().parent
project=root.parent.parent
batch=root
sys.path.insert(0,str(batch/'code'))
from tooluse_pilot import executable_runner as runner
from openai import OpenAI
case,attempt=sys.argv[1:3]
out=root/f'case-{case}-attempt-{attempt}'
out.mkdir(exist_ok=False)
os.chdir(out)
config=project/'gateway.local.example.json'
cfg=json.loads(config.read_text(encoding='utf-8'));model=cfg['models']['qwen']
state={'pid':os.getpid(),'case':case,'attempt':attempt,'completed_requests':0,'successes':0,'errors':0,'status':'starting'}
def save():
    state['updated_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (out/'live.json').write_text(json.dumps(state,indent=2),encoding='utf-8')
original_record=runner.record
def record(*args,**kwargs):
    value=original_record(*args,**kwargs)
    state['completed_requests']+=1
    state['successes' if kwargs['status']=='ok' else 'errors']+=1
    state['last_error']=kwargs.get('error')
    state['last_completed_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    state['status']='between_requests';save()
    return value
runner.record=record
client=OpenAI(api_key=model.get('api_key') or os.environ[cfg.get('api_key_env','MODEL_API_KEY')],base_url=os.environ[model.get('base_url_env',cfg.get('base_url_env','MODEL_BASE_URL'))],timeout=cfg.get('timeout_sec',180),max_retries=0)
create=client.chat.completions.create
def tracked_create(**kwargs):
    state['current_request_started_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    state['status']='request_pending';save()
    return create(**kwargs)
client.chat.completions.create=tracked_create
save();print(json.dumps({'pid':os.getpid(),'output':str(out)}),flush=True)
try:
    result=runner.run_candidate(batch/'candidates'/f'case-{case}'/'candidate.json',config,'qwen',out/'usage.sqlite',25,80,client_factory=lambda:client)
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    state['status']='completed';state['state']=result['state'];state['score']=result['score'];save()
    print(json.dumps({k:result.get(k) for k in ['state','requests','tool_calls','invalid_tool_actions','score','artifact_dir']},indent=2),flush=True)
finally:client.close()
