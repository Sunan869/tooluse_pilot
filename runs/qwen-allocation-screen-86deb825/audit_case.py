"""Offline replay, preserving original run data; no model client."""
import json,sys,shutil,importlib.util,hashlib
from pathlib import Path
from openpyxl import load_workbook
root=Path(__file__).resolve().parent
batch=root.parent/'allocation-batch-v1-20261026'
sys.path.insert(0,str(batch/'code'))
from tooluse_pilot.allocation_task import Environment
spec=importlib.util.spec_from_file_location('oracle',batch/'verify_batch.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
case,attempt=sys.argv[1:3]
out=root/f'case-{case}-attempt-{attempt}'
run=json.loads((out/'result.json').read_text(encoding='utf-8'))
artifact=out/run['artifact_dir']
source=batch/'candidates'/f'case-{case}'
replay=out/'offline-replay'
shutil.copytree(source,replay)
env=Environment(json.loads((source/'candidate.json').read_text(encoding='utf-8')),replay)
diff=[];errors=[];index=0
for e in run['events']:
    if e.get('event')!='tool_call':continue
    index+=1
    try:actual={'ok':True,'result':env.call(e['tool'],json.loads(e['arguments']))}
    except Exception as exc:
        actual={'ok':False,'error':str(exc)};env.invalid_actions+=1
        errors.append({'index':index,'tool':e['tool'],'error':str(exc)})
    if actual!=e['result']:diff.append({'index':index,'expected':e['result'],'replay':actual})
score=env.score();env.close()
w=load_workbook(artifact/'reconciliation.xlsx',read_only=True,data_only=True)
expected,decisions=oracle.independent(w)
summary=[str(w['Summary'][c].value or '') for c in ['B2','B3','B4','B5']]
saved=[list(r) for r in list(w['Decisions'].values)[1:]]
stage='revised' if w['Policy']['B3'].value=='Beijing,Shenzhen' else 'initial'
w.close()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
record={'replay_mismatches':diff,'replay_score':score,'tool_errors':errors,'api_errors':[e for e in run['events'] if e.get('event')=='api_attempt' and e.get('error')],'independent_expected':expected,'actual':summary,'stage':stage,'decisions_mismatches':[{'expected':a,'actual':b} for a,b in zip(decisions,saved) if a!=b],'decision_row_count_matches':len(decisions)==len(saved),'source_candidate_hash_matches':sha(source/'candidate.json')==sha(artifact/'candidate.json'),'requests':run['requests'],'tool_calls':run['tool_calls']}
with (out/'AUDIT.json').open('x',encoding='utf-8') as f:json.dump(record,f,indent=2)
print(json.dumps(record,indent=2))
