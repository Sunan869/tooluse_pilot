import sys,json,shutil,hashlib,difflib
from pathlib import Path
from openpyxl import load_workbook
base=Path(__file__).resolve().parent
project=base.parent.parent
out=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else base
if out!=base:out.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(base/'code'))
from tooluse_pilot.real_w6_reconciliation import Environment,oracle,initial_diagnostics
source=project/'runs/qwen-confirmation-20261026/candidate-expanded'
cases={'gpt':project/'runs/gpt-29row-20261026-154836-5500c2c6/result.json', 'qwen1':project/'runs/qwen-confirmation-20261026/qwen-expanded-1.json','qwen2':project/'runs/qwen-confirmation-20261026/qwen-expanded-2.json'}
results={}
for name,path in cases.items():
    run=json.loads(path.read_text(encoding='utf-8-sig'))
    dest=out/('replay-'+name)
    shutil.copytree(source,dest)
    case=json.loads((dest/'candidate.json').read_text())
    env=Environment(case,dest);rejections=[];mismatches=[];tool_index=0
    for event in run['events']:
        if event.get('event')!='tool_call':continue
        tool_index+=1;args=json.loads(event['arguments']);historical=event['result']
        if historical.get('ok') is False:
            reasons=None
            if event['tool']=='receive_update' and args=={} and not env.transitioned:
                wb=load_workbook(env.path,read_only=True,data_only=True)
                try:
                    expected=oracle(wb);actual=tuple(str(wb['Summary'][c].value or '') for c in ['B2','B3','B4','B5'])
                finally:wb.close()
                report=(dest/'report.txt').read_text() if (dest/'report.txt').exists() else ''
                reasons=initial_diagnostics(expected,actual,report,env.saved_before)
            rejections.append({'tool_index':tool_index,'tool':event['tool'],'arguments':args,'historical_result':historical,'v2_remaining_reasons':reasons,'grader_false_rejection':reasons==[]})
            # Retain historical control flow: a rejected gate never transitioned.
            env.invalid_actions+=1
            continue
        try:payload={'ok':True,'result':env.call(event['tool'],args)}
        except Exception as exc:payload={'ok':False,'error':str(exc)}
        if payload!=historical:mismatches.append({'tool_index':tool_index,'historical':historical,'v2':payload})
    score=env.score();env.close()
    false_count=sum(x['grader_false_rejection'] for x in rejections)
    results[name]={'source':str(path),'original_score':run['score'],'original_invalid_actions':run['invalid_tool_actions'],'historical_control_flow_replay_score_v2':score,'rejections':rejections,'successful_tool_replay_mismatches':mismatches,'grader_false_rejection_count':false_count,'remaining_model_invalid_actions':run['invalid_tool_actions']-false_count,'final_deliverables_and_stage_checks_pass':all(score['checks'].values()),'independent_adjusted_verdict':all(score['checks'].values()) and run['invalid_tool_actions']==false_count,'note':'Original invalid actions and gate events are preserved. Adjusted verdict is an offline adjudication, not a rewritten run or new execution.'}
    assert not mismatches
assert results['gpt']['grader_false_rejection_count']==1 and results['gpt']['independent_adjusted_verdict']
assert not results['qwen1']['independent_adjusted_verdict'] and not results['qwen2']['independent_adjusted_verdict']
originals=json.loads((base/'original-hashes.json').read_text())
assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in originals.items())
(out/'offline-verdicts-v2.json').write_text(json.dumps({'version':'report-fields-v2','model_calls':0,'original_hashes_verified':len(originals),'results':results},indent=2))
print(json.dumps({k:{'adjusted':v['independent_adjusted_verdict'],'original_invalid':v['original_invalid_actions'],'false_rejections':v['grader_false_rejection_count'],'remaining_invalid':v['remaining_model_invalid_actions']} for k,v in results.items()},indent=2))
