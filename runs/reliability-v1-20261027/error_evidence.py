import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;plan=json.loads((ROOT/'MANIFEST.json').read_text());items=[]
for run in plan['runs']:
 p=ROOT/run['output'];audit=p/'audit/AUDIT.json'
 if not audit.exists():continue
 a=json.loads(audit.read_text(encoding='utf-8'));raw=json.loads((p/'result.json').read_text(encoding='utf-8'));events=[e for e in raw['events'] if e['event']=='tool_call'];errors=[{'tool_index':i+1,'tool':e['tool'],'arguments':e['arguments'],'response':e['result']} for i,e in enumerate(events) if not e['result']['ok'] or e['result'].get('result',{}).get('accepted') is False or e['result'].get('result',{}).get('success') is False]
 details={'case':run['case'],'repeat':run['repeat'],'business_correct':a['business_correct'],'observable_labels':a['labels_observable_not_causal'],'causal_attribution':'unknown unless directly supported by a rejected operation or final state mismatch','actual':a['actual'],'independent_gold':a['gold'],'tool_rejections':errors,'result_path':str((p/'result.json').resolve())}
 if a['family'] in (7,8):
  details['authority_cache_read']=any(e['tool']=='read_rows' and json.loads(e['arguments']).get('source')=='cache' for e in events)
  details['coverage_complete']=a['coverage_complete']
  if a['family']==8:details['version_events']=[{'tool_index':i+1,'tool':e['tool'],'read_revision':e['result'].get('result',{}).get('read_revision'),'current_revision':e['result'].get('result',{}).get('current_revision'),'stale':e['result'].get('result',{}).get('stale')} for i,e in enumerate(events) if 'current_revision' in e['result'].get('result',{})]
 else:details['fault_exposed']=a['fault_exposed']
 items.append(details)
(ROOT/'ERROR-EVIDENCE.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8');print('Evidence rows: '+str(len(items)))
