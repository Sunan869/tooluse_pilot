import json,hashlib,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent
plan=json.loads((ROOT/'MANIFEST.json').read_text());progress=json.loads((ROOT/'BATCH-PROGRESS.json').read_text());assert progress['status']=='completed' and progress['completed']==36 and not (ROOT/'BATCH.lock').exists()
checks=[]
for item in plan['runs']:
 run=ROOT/item['output'];result=json.loads((run/'result.json').read_text(encoding='utf-8'));a=json.loads((run/'audit/AUDIT.json').read_text(encoding='utf-8'));assert hashlib.sha256((run/'result.json').read_bytes()).hexdigest()==a['result_sha256']
 events=[e for e in result['events'] if e['event']=='api_attempt'];wire=[json.loads(x) for x in (run/'wire-requests.jsonl').read_text().splitlines()];responses=[json.loads(x) for x in (run/'responses.jsonl').read_text().splitlines()]
 db=sqlite3.connect((run/'usage.sqlite').as_uri()+'?mode=ro',uri=True);count,errors,last,nruns=db.execute("select count(*),sum(status='error'),max(attempt),count(distinct run_id) from requests").fetchone();models=[x[0] for x in db.execute('select distinct model from requests')];db.close()
 assert count==result['requests']==len(events)==last and nruns==1 and count<=25 and result['tool_calls']<=80 and models==['Qwen3.8-Flash-Next-AWQ-INT4']
 assert len(responses)==count-errors and len(wire)<=count
 if errors==0:assert len(wire)==count
 assert all(x['model']=='Qwen3.8-Flash-Next-AWQ-INT4' for x in responses)
 assert a['tools']==result['tool_calls']
 if result['task_completed']:assert result['events'][-1]['event']=='tool_call' and result['events'][-1]['tool']=='finish'
 checks.append({'run':item['output'],'ledger_requests':count,'wire_requests':len(wire),'responses':len(responses),'errors':errors,'tools_replayed':a['tools']})
assert sum(c['ledger_requests'] for c in checks)<=900
frozen=json.loads((ROOT/'FROZEN-HASHES.json').read_text());assert all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==h for p,h in frozen.items())
for name in ('w7-paired-v1-20261027','w8-version-pair-v1-20261027','w9-routing-pair-v1-20261027'):
 old=ROOT.parent/name;m=json.loads((old/'FINAL-MANIFEST.json').read_text());assert all(hashlib.sha256((old/p).read_bytes()).hexdigest()==h for p,h in m.items())
(ROOT/'FINAL-INTEGRITY.json').write_text(json.dumps({'runs':checks,'actual_api_requests':sum(c['ledger_requests'] for c in checks),'API_errors':sum(c['errors'] for c in checks),'exact_replayed_tools':sum(c['tools_replayed'] for c in checks),'frozen_hashes_unchanged':True,'historical_evidence_unchanged':True,'real_GPT_calls':0},indent=2),encoding='utf-8')
manifest={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob('*') if p.is_file() and '__pycache__' not in str(p) and p.name!='DELIVERY-HASHES.json'}
(ROOT/'DELIVERY-HASHES.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');print(json.dumps({'runs':36,'API_requests':sum(c['ledger_requests'] for c in checks),'errors':sum(c['errors'] for c in checks),'replayed_tools':sum(c['tools_replayed'] for c in checks),'hashed_files':len(manifest)}))
