"""Read-only source audit; replay and reports go to a new audit subdirectory."""
import json,sys,shutil,hashlib,sqlite3,importlib.util
from pathlib import Path
from openpyxl import load_workbook
HERE=Path(__file__).resolve().parent;root=HERE.parents[1]
base=root/'runs/reservation-state-v4-20261027'
src=root/'runs/gpt-reservation-state-v4-20261027-102457-aaefe798/case-4'
out=HERE/(sys.argv[1] if len(sys.argv)>1 else 'audit-1');out.mkdir(exist_ok=False)
sys.path.insert(0,str(base/'code'))
from tooluse_pilot.reservation_task import Environment
spec=importlib.util.spec_from_file_location('independent_v4',base/'independent_oracle.py');oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
q=json.loads((src/'result.json').read_text(encoding='utf-8'));artifact=src/q['artifact_dir']
hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in src.rglob('*') if p.is_file()}
assert q==json.loads((artifact/'run_result.json').read_text(encoding='utf-8'))
case=json.loads((base/'candidates/case-4/candidate.json').read_text(encoding='utf-8'))
assert (artifact/'candidate.json').read_bytes()==(base/'candidates/case-4/candidate.json').read_bytes()
shutil.copytree(base/'candidates/case-4',out/'offline-replay');env=Environment(case,out/'offline-replay')
diff=[];stages=[];groups=[];group=None;tool_index=0
for e in q['events']:
    if e['event']=='api_attempt':
        group={'turn':e['turn'],'attempt':e['attempt'],'error':e['error'],'tools':[]};groups.append(group);continue
    if e['event']!='tool_call':continue
    tool_index+=1;args=json.loads(e['arguments']);group['tools'].append({'index':tool_index,'name':e['tool'],'sheet':args.get('sheet')})
    if e['tool'] in ['receive_update','finish']:
        w=load_workbook(env.path,read_only=True,data_only=True)
        expected,rows=oracle.independent(w);actual=[str(w['Summary'][c].value) for c in ['B2','B3','B4','B5']]
        saved=[list(r) for r in list(w['Decisions'].values)[1:]];stage=int(w['Stage']['B2'].value);w.close()
        assert expected==actual and rows==saved
        stages.append({'round':stage,'gate':e['tool'],'tool_index':tool_index,'expected':expected,'actual':actual,'all_decisions_match':True,'decisions':saved})
        shutil.copy2(env.path,out/f'round-{stage}-before-gate.xlsx')
    try:actual_result={'ok':True,'result':env.call(e['tool'],args)}
    except Exception as exc:actual_result={'ok':False,'error':str(exc)};env.invalid_actions+=1
    if actual_result!=e['result']:diff.append({'index':tool_index,'logged':e['result'],'replayed':actual_result})
score=env.score();env.close();assert score['success'] and not diff and tool_index==49 and len(stages)==3
conn=sqlite3.connect('file:'+str((src/'usage.sqlite').resolve().as_posix())+'?mode=ro',uri=True);conn.row_factory=sqlite3.Row
ledger=[dict(r) for r in conn.execute('select attempt,model,provider,status,error,duration_ms,prompt_tokens,completion_tokens,tool_calls from requests order by rowid')];conn.close()
assert len(ledger)==q['requests']==14 and all(x['status']=='ok' and not x['error'] for x in ledger)
provenance=json.loads((base/'provenance.json').read_text(encoding='utf-8'))
assert all(hashlib.sha256((base/n).read_bytes()).hexdigest()==h for n,h in provenance['hashes'].items())
record={'source':str(src),'artifact':str(artifact),'requested_model':q['model'],'protocol':q['protocol'],'requests':14,'tool_calls':49,'invalid_actions':0,'api_errors':0,'replay_mismatches':diff,'score':score,'stages':stages,'tool_groups':groups,'ledger':ledger,'original_hashes':hashes,'source_hashes_match_frozen_v4':True,'model_calls_by_audit':0,'limits':'Model labels do not authenticate backend weights. Current source hashes match frozen V4, but are not independent proof of historical process imports.'}
assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in hashes.items())
(out/'GPT-V4-AUDIT.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
print(json.dumps({'requests':14,'tools':49,'stages':[{'round':s['round'],'expected':s['expected'],'all_decisions_match':True} for s in stages],'groups':groups,'score_success':True},indent=2))
