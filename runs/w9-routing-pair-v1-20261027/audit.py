import sys,json,shutil,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from tooluse_pilot.w9_task import Environment
from independent_graph import oracle
run=ROOT/sys.argv[1];result=json.loads((run/'result.json').read_text(encoding='utf-8'));artifact=run/result['artifact_dir'];out=run/(sys.argv[2] if len(sys.argv)>2 else 'audit');out.mkdir(exist_ok=False)
case=json.loads((artifact/'candidate.json').read_text(encoding='utf-8'));data=json.loads((artifact/'dataset.json').read_text(encoding='utf-8'));replay=out/'replay';replay.mkdir()
for name in ('candidate.json','dataset.json'):shutil.copy2(artifact/name,replay/name)
e=Environment(case,replay);count=0
for event in result['events']:
 if event['event']!='tool_call':continue
 try:actual={'ok':True,'result':e.call(event['tool'],json.loads(event['arguments']))}
 except Exception as exc:e.invalid_actions+=1;actual={'ok':False,'error':str(exc)[:300]}
 assert actual==event['result'],(count,actual,event['result']);count+=1
assert e.score()==result['score'];state=json.loads((artifact/'state.json').read_text());gold=oracle(data,case['condition'])
# Reconstruct transport independently from ledger and fixed timetable, without calling environment score.
location=data['start'];time=data['start_time'];cost=0;ids=[]
for entry in state['charges']:
 route=next(r for r in data['routes'] if r['route_id']==entry['route_id']);assert route['origin']==location and route['departure']>=time
 assert entry['amount']==route['cost'] and entry['departure']==route['departure'] and entry['arrival']==route['arrival']
 assert case['condition']!='permanent' or route['route_id']!=data['fault_route']
 location=route['destination'];time=route['arrival'];cost+=route['cost'];ids.append(route['route_id'])
independent_checks={'arrived':location==data['destination'],'deadline':time<=data['deadline'],'budget':cost<=data['budget'],'minimum_cost':cost==gold['minimum_cost'],'no_duplicate_charges':len(ids)==len(set(ids)) and cost==state['package']['total_cost']}
assert independent_checks==result['score']['checks'];assert all(independent_checks.values())==result['score']['answer_success']
wire=[json.loads(s) for s in (run/'wire-requests.jsonl').read_text().splitlines()];responses=[json.loads(s) for s in (run/'responses.jsonl').read_text().splitlines()]
assert all(w['url']=='http://10.10.23.7:5610/v1/chat/completions' and w['model']=='Qwen3.8-Flash-Next-AWQ-INT4' and w['chat_template_kwargs']=={'enable_thinking':False} for w in wire)
errors=sum(bool(x['error']) for x in result['events'] if x['event']=='api_attempt');summary={'run':run.name,'condition':case['condition'],'renamed':case['renamed'],'success':result['score']['success'],'independent_checks':independent_checks,'oracle':gold,'path':ids,'cost':cost,'fault_exposed':result['score']['fault_exposed'],'permanent_retries':result['score']['permanent_retries'],'rejections':result['score']['rejections'],'api_attempts':result['requests'],'wire_requests':len(wire),'successful_responses':len(responses),'api_errors':errors,'tools_replayed_exactly':count,'invalid_actions':result['invalid_tool_actions'],'stop_reason':result['state'],'response_models':sorted({r['model'] for r in responses}),'dataset_sha256':hashlib.sha256((artifact/'dataset.json').read_bytes()).hexdigest(),'candidate_sha256':hashlib.sha256((artifact/'candidate.json').read_bytes()).hexdigest()}
(out/'AUDIT.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
