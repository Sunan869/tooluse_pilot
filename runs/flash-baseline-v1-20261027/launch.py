import sys,os,json,datetime
from pathlib import Path
root=Path(__file__).resolve().parent
project=root.parent.parent
batch=root
sys.path.insert(0,str(batch/'code'))
from tooluse_pilot import executable_runner as runner
from openai import OpenAI
import httpx,hashlib
case,attempt=sys.argv[1:3]
out=root/f'case-{case}-attempt-{attempt}'
out.mkdir(exist_ok=False)
os.chdir(out)
config=root/'gateway.flash.isolated.json'
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
def capture_request(request):
    body=json.loads(request.content)
    assert str(request.url)=='http://10.10.23.7:5610/v1/chat/completions'
    assert body['model']=='Qwen3.8-Flash-Next-AWQ-INT4'
    assert body['chat_template_kwargs']['enable_thinking'] is False
    item={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'url':str(request.url),'model':body['model'],'chat_template_kwargs':body['chat_template_kwargs'],'body_sha256':hashlib.sha256(request.content).hexdigest()}
    with (out/'wire-requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(item)+'\n')
transport=httpx.Client(event_hooks={'request':[capture_request]})
client=OpenAI(http_client=transport,api_key=model.get('api_key') or os.environ[cfg.get('api_key_env','MODEL_API_KEY')],base_url=os.environ[model.get('base_url_env',cfg.get('base_url_env','MODEL_BASE_URL'))],timeout=cfg.get('timeout_sec',180),max_retries=0)
create=client.chat.completions.create
def tracked_create(**kwargs):
    state['current_request_started_at']=datetime.datetime.now(datetime.timezone.utc).isoformat()
    state['status']='request_pending';save()
    response=create(**kwargs)
    with (out/'responses.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(response.model_dump(exclude_none=True))+'\n')
    return response
client.chat.completions.create=tracked_create
save();print(json.dumps({'pid':os.getpid(),'output':str(out)}),flush=True)
try:
    result=runner.run_candidate(batch/'candidates'/f'case-{case}'/'candidate.json',config,'qwen',out/'usage.sqlite',25,80,client_factory=lambda:client)
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    state['status']='completed';state['state']=result['state'];state['score']=result['score'];save()
    print(json.dumps({k:result.get(k) for k in ['state','requests','tool_calls','invalid_tool_actions','score','artifact_dir']},indent=2),flush=True)
finally:client.close()
