"""User-operated GPT comparison. Default is a zero-network plan preview."""
import argparse,json,os,sys,datetime,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
def main():
 p=argparse.ArgumentParser();p.add_argument('--output-root',required=True);p.add_argument('--config',default=str(ROOT.parent.parent/'gateway.models.json'));p.add_argument('--execute',action='store_true');a=p.parse_args()
 config=Path(a.config).resolve();cfg=json.loads(config.read_text(encoding='utf-8-sig'));model=cfg['models']['gpt'];assert model['model']=='gpt-6-astra','Existing gpt alias changed; review before execution'
 plan=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'));hashes=json.loads((ROOT/'FROZEN-HASHES.json').read_text());assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in hashes.items())
 details={'model':model['model'],'case_count':12,'repeats':1,'max_attempts_each':25,'max_tools_each':80,'max_total_attempts':300,'output_root':str(Path(a.output_root).resolve()),'execute':a.execute};print(json.dumps(details,ensure_ascii=False),flush=True)
 if not a.execute:return
 keyenv=cfg.get('api_key_env','MODEL_API_KEY');baseenv=model.get('base_url_env',cfg.get('base_url_env','MODEL_BASE_URL'))
 if not os.environ.get(baseenv) or not (model.get('api_key') or os.environ.get(keyenv)):raise RuntimeError('Set the existing model base URL/key in this terminal first; do not share credentials.')
 from tooluse_pilot import executable_runner as runner
 from openai import OpenAI
 import httpx
 out=Path(a.output_root).resolve();out.mkdir(parents=True,exist_ok=True);identity={'manifest_sha256':hashlib.sha256((ROOT/'MANIFEST.json').read_bytes()).hexdigest(),'frozen_hashes_sha256':hashlib.sha256((ROOT/'FROZEN-HASHES.json').read_bytes()).hexdigest(),'config_sha256':hashlib.sha256(config.read_bytes()).hexdigest(),'model':model['model'],'cases':[c['case'] for c in plan['cases']],'repeats':1,'max_total_attempts':300}
 meta=out/'comparison-plan.json'
 if meta.exists():assert json.loads(meta.read_text())==identity,'Resume identity differs; do not mix experiments'
 else:
  if any(out.iterdir()):raise RuntimeError('Output directory must be empty or contain matching comparison-plan.json')
  meta.write_text(json.dumps(identity,indent=2),encoding='utf-8')
 lock=out/'RUNNING.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
 try:
  summaries=[]
  for c in plan['cases']:
   dest=out/c['case'];resultfile=dest/'result.json'
   if resultfile.exists():result=json.loads(resultfile.read_text(encoding='utf-8'))
   else:
    if dest.exists():raise RuntimeError('Incomplete/uncertain case; inspect before retrying: '+str(dest))
    dest.mkdir();old=Path.cwd();os.chdir(dest)
    def capture(request):
     body=json.loads(request.content);entry={'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'model':body.get('model'),'url_host':request.url.host,'url_path':request.url.path,'body_sha256':hashlib.sha256(request.content).hexdigest()}
     assert body.get('model')==model['model']
     with (dest/'wire-requests.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(entry)+'\n')
    client=OpenAI(api_key=model.get('api_key') or os.environ[keyenv],base_url=os.environ[baseenv],timeout=cfg.get('timeout_sec',300),max_retries=0,http_client=httpx.Client(event_hooks={'request':[capture]}))
    target=client.responses if model.get('api_type')=='responses' else client.chat.completions;original=target.create
    def tracked(**kwargs):
     response=original(**kwargs)
     with (dest/'responses.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(response.model_dump(exclude_none=True))+'\n')
     return response
    target.create=tracked
    try:
     result=runner.run_candidate(ROOT/'candidates'/('case-'+c['case'])/'candidate.json',config,'gpt',dest/'usage.sqlite',25,80,client_factory=lambda:client)
     resultfile.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    finally:client.close();os.chdir(old)
   assert result['model']==model['model'] and result['requests']<=25
   summaries.append({'case':c['case'],'model':result['model'],'state':result['state'],'requests':result['requests'],'tool_calls':result['tool_calls'],'score':result['score'],'result':str(resultfile)})
   assert sum(s['requests'] for s in summaries)<=300
   (out/'comparison-summary.json').write_text(json.dumps(summaries,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:summaries[-1][k] for k in ('case','state','requests','tool_calls')},ensure_ascii=False),flush=True)
  print('Results: '+str(out),flush=True)
 finally:lock.unlink()
if __name__=='__main__':main()
