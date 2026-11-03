import json,csv,collections,statistics,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent
plan=json.loads((ROOT/'MANIFEST.json').read_text(encoding='utf-8'));rows=[]
for item in plan['runs']:
 p=ROOT/item['output']/'audit/AUDIT.json'
 if p.exists():
  row=dict(json.loads(p.read_text(encoding='utf-8')),case=item['case'],repeat=item['repeat'])
  raw=json.loads((p.parent.parent/'result.json').read_text(encoding='utf-8'))
  errors=[e['result'].get('error','') for e in raw['events'] if e['event']=='tool_call' and not e['result']['ok']]
  row['input_format_errors']=sum('rows_json needs' in e or 'Expecting' in e for e in errors)
  row['invalid_cursor_errors']=sum('Invalid cursor' in e for e in errors)
  rows.append(row)
if '--partial' not in sys.argv:assert len(rows)==36,'Wait for all 36 runs; do not drop incomplete outcomes'
def metrics(group):
 n=len(group)
 return {'runs':n,'business_correct':sum(r['business_correct'] for r in group),'business_accuracy':sum(r['business_correct'] for r in group)/n if n else None,'completed':sum(r['task_completed'] for r in group),'correct_and_completed':sum(r['success'] for r in group),'budget_exhausted':sum(r['budget_exhausted'] for r in group),'runs_with_invalid_tool_actions':sum(r['invalid_actions']>0 for r in group),'invalid_tool_actions':sum(r['invalid_actions'] for r in group),'input_format_errors':sum(r['input_format_errors'] for r in group),'invalid_cursor_errors':sum(r['invalid_cursor_errors'] for r in group),'runs_with_API_errors':sum(r['api_errors']>0 for r in group),'API_errors':sum(r['api_errors'] for r in group),'API_attempts':sum(r['requests'] for r in group),'tool_calls':sum(r['tools'] for r in group),'runs_with_recoverable_rejections':sum(r['recoverable_rejections']>0 for r in group),'recovered_after_rejection_success':sum(r['recovered_after_rejection_success'] for r in group),'fault_exposed':sum(r['fault_exposed'] is True for r in group),'API_clean_business_correct':sum(r['business_correct'] for r in group if not r['api_errors']),'API_clean_runs':sum(not r['api_errors'] for r in group)}
families={str(f):metrics([r for r in rows if r['family']==f]) for f in (7,8,9)};percase=[]
for c in plan['cases']:
 group=[r for r in rows if r['case']==c['case']];percase.append({'case':c['case'],'family':c['family'],'condition':c['condition'],'seed':c['seed'],'observed_repeats':len(group),'business_correct_repeats':sum(r['business_correct'] for r in group),'successful_repeats':sum(r['success'] for r in group),'all_three_business_correct':len(group)==3 and all(r['business_correct'] for r in group),'all_three_successful':len(group)==3 and all(r['success'] for r in group)})
index={(r['case'],r['repeat']):r for r in rows};pairs=[]
for rep in (1,2,3):
 for seed in (20261030,20261031):
  for cond in ('coverage','conflict'):
   pairs.append((f'W7-{cond}',seed,rep,f'w7-{seed}-clean',f'w7-{seed}-{cond}'))
  pairs.append(('W8-dynamic',seed,rep,f'w8-{seed}-static',f'w8-{seed}-dynamic'))
 pairs.append(('W9-permanent',None,rep,'w9-fixed-transient','w9-fixed-permanent'))
paired=[]
for label,seed,rep,base,challenge in pairs:
 if (base,rep) not in index or (challenge,rep) not in index:continue
 a=index[base,rep];b=index[challenge,rep];paired.append({'contrast':label,'seed':seed,'repeat':rep,'baseline_correct':a['business_correct'],'challenge_correct':b['business_correct'],'difference_challenge_minus_base':int(b['business_correct'])-int(a['business_correct']),'baseline_fault_exposed':a['fault_exposed'],'challenge_fault_exposed':b['fault_exposed']})
pairsummary={}
for label in sorted({p['contrast'] for p in paired}):
 group=[p for p in paired if p['contrast']==label];pairsummary[label]={'pairs':len(group),'mean_paired_difference':statistics.mean(p['difference_challenge_minus_base'] for p in group),'baseline_correct_challenge_wrong':sum(p['baseline_correct'] and not p['challenge_correct'] for p in group),'baseline_wrong_challenge_correct':sum(not p['baseline_correct'] and p['challenge_correct'] for p in group),'both_wrong':sum(not p['baseline_correct'] and not p['challenge_correct'] for p in group),'both_correct':sum(p['baseline_correct'] and p['challenge_correct'] for p in group)}
result={'complete':len(rows)==36,'overall':metrics(rows),'by_family':families,'case_macro_accuracy':statistics.mean(c['business_correct_repeats']/c['observed_repeats'] for c in percase if c['observed_repeats']) if rows else None,'equal_family_macro_accuracy':statistics.mean(m['business_accuracy'] for m in families.values() if m['runs']) if rows else None,'case_stability':{'denominator_cases':12,'cases_with_3_of_3_business_correct':sum(c['all_three_business_correct'] for c in percase),'cases_with_3_of_3_successful':sum(c['all_three_successful'] for c in percase)},'per_case':percase,'paired_contrasts':pairsummary,'paired_details':paired,'observable_error_labels':dict(collections.Counter(label for r in rows for label in r['labels_observable_not_causal'])),'limitations':['Purpose-built small cases; not a representative model ranking.','Repeats share base tasks and are correlated; no confidence intervals or significance claims.','Paired differences retain baseline failures and unexposed faults; not a causal estimate from every pair.','Business correctness checks saved content/final business conditions; completion and correct-and-completed are separate.','Error labels describe observable mismatches, not internal model reasoning or exclusive causal classes.'],'GPT_comparison':{'cases':12,'repeats':1,'max_API_attempts':300,'comparison_Qwen_repeat':1,'automatically_executed':False}}
name='PARTIAL' if '--partial' in sys.argv else 'SUMMARY';(ROOT/(name+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
if name=='SUMMARY':
 fields=['case','repeat','family','condition','business_correct','task_completed','success','budget_exhausted','requests','api_errors','tools','invalid_actions','recoverable_rejections','recovered_after_rejection_success','fault_exposed','coverage_complete','revision_current','labels_observable_not_causal','input_format_errors','invalid_cursor_errors']
 with (ROOT/'runs.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for row in rows:w.writerow({k:json.dumps(row[k],ensure_ascii=False) if isinstance(row[k],list) else row[k] for k in fields})
print(json.dumps({'completed':len(rows),'overall':result['overall'],'by_family':families}))
