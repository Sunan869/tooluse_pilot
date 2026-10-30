import sys,json,os,subprocess,datetime,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent
from audit import audit
plan=json.loads((ROOT/'MANIFEST.json').read_text());hashes=json.loads((ROOT/'FROZEN-HASHES.json').read_text());assert all(hashlib.sha256((ROOT/k).read_bytes()).hexdigest()==v for k,v in hashes.items())
lock=ROOT/'BATCH.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode());os.close(fd)
try:
 completed=[]
 for item in plan['runs']:
  out=ROOT/item['output']
  if not (out/'result.json').exists():
   if out.exists():raise RuntimeError('Uncertain incomplete run; inspect before any retry: '+str(out))
   progress={'pid':os.getpid(),'current':item,'completed':len(completed),'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'running'};(ROOT/'BATCH-PROGRESS.json').write_text(json.dumps(progress,indent=2))
   logs=ROOT/'controller-logs';logs.mkdir(exist_ok=True)
   with (logs/(item['output']+'.stdout.txt')).open('xb') as stdout,(logs/(item['output']+'.stderr.txt')).open('xb') as stderr:
    proc=subprocess.run([sys.executable,str(ROOT/'launch.py'),item['case'],str(item['repeat'])],stdout=stdout,stderr=stderr)
   if proc.returncode:raise RuntimeError('Pipeline child failed: '+item['output'])
  summary=audit(out);completed.append(summary)
  assert sum(x['requests'] for x in completed)<=900
  progress={'pid':os.getpid(),'completed':len(completed),'last_run':item['output'],'last_success':summary['success'],'requests_completed':sum(x['requests'] for x in completed),'updated_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'status':'checkpoint'};(ROOT/'BATCH-PROGRESS.json').write_text(json.dumps(progress,indent=2));print(json.dumps(progress),flush=True)
  if '--smoke' in sys.argv:break
 if len(completed)==len(plan['runs']):progress['status']='completed';(ROOT/'BATCH-PROGRESS.json').write_text(json.dumps(progress,indent=2))
finally:lock.unlink()
