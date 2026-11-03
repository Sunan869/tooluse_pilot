import json,copy,heapq
from pathlib import Path

def clock(minutes):return f'{minutes//60:02d}:{minutes%60:02d}'
def minimum_cost(data,condition):
 queue=[(0,data['start_time'],data['start'])]
 while queue:
  cost,time,node=heapq.heappop(queue)
  if node==data['destination']:return cost
  for r in data['routes']:
   if condition=='permanent' and r['route_id']==data['fault_route']:continue
   if r['origin']==node and r['departure']>=time and r['arrival']<=data['deadline'] and cost+r['cost']<=data['budget']:heapq.heappush(queue,(cost+r['cost'],r['arrival'],r['destination']))
 return None
class Environment:
 terminal_stops_runner=True
 def __init__(self,case,folder):
  self.case=case;self.folder=Path(folder);self.data=json.loads((self.folder/case['input']['dataset']).read_text(encoding='utf-8'));self.location=self.data['start'];self.time=self.data['start_time'];self.cost=0;self.charges=[];self.calls=[];self.finished=False;self.invalid_actions=0;self.fault_attempts=0;self.rejections=[]
 def package(self):return {'package_id':self.data['package_id'],'location':self.location,'virtual_time':clock(self.time),'destination':self.data['destination'],'deadline':clock(self.data['deadline']),'budget':self.data['budget'],'total_cost':self.cost,'hubs':self.data['hubs'],'rules':'Queries do not advance time. Any hub may be queried. Successful sends wait until departure and arrive atomically; failures do not move or charge. Cannot board an already departed leg. Incident status can be inspected. finish is terminal and does not grade correctness.'}
 def call(self,name,args):
  if self.finished:raise ValueError('Task is terminal')
  if name=='get_package':result=self.package()
  elif name=='list_routes':
   routes=[dict(r,departure=clock(r['departure']),arrival=clock(r['arrival'])) for r in self.data['routes'] if r['origin']==args['origin']];result={'origin':args['origin'],'complete':True,'total':len(routes),'routes':routes}
  elif name=='inspect_incident':
   if args['incident_id']!='I001' or not self.fault_attempts:result={'found':False,'incident_id':args['incident_id']}
   else:result={'found':True,'incident_id':'I001','route_id':self.data['fault_route'],'kind':self.case['condition'],'status':'resolved' if self.case['condition']=='transient' else 'permanent_for_episode','moved':False,'charged':0}
  elif name=='get_ledger':result={'charges':copy.deepcopy(self.charges),'total_cost':self.cost,'complete':True}
  elif name=='send_leg':
   route=next((r for r in self.data['routes'] if r['route_id']==args['route_id']),None);code=None
   if route is None:code='UNKNOWN_ROUTE'
   elif route['origin']!=self.location:code='WRONG_ORIGIN'
   elif route['departure']<self.time:code='MISSED_DEPARTURE'
   elif self.cost+route['cost']>self.data['budget']:code='BUDGET_EXCEEDED'
   elif route['route_id']==self.data['fault_route'] and (self.fault_attempts==0 or self.case['condition']=='permanent'):
    self.fault_attempts+=1;code='E503'
   if code:
    result={'success':False,'code':code,'moved':False,'charged':0}
    if code=='E503':result.update(incident_id='I001',message='Dispatch unavailable. No movement or charge. inspect_incident can determine incident status.')
    self.rejections.append({'route_id':args['route_id'],'code':code})
   else:
    self.location=route['destination'];self.time=route['arrival'];self.cost+=route['cost'];charge={'entry_id':f'L{len(self.charges)+1:03d}','route_id':route['route_id'],'origin':route['origin'],'destination':route['destination'],'departure':route['departure'],'arrival':route['arrival'],'amount':route['cost']};self.charges.append(charge)
    result={'success':True,'location':self.location,'virtual_time':clock(self.time),'charged':route['cost'],'total_cost':self.cost,'ledger_entry_id':charge['entry_id']}
  elif name=='finish':self.finished=True;result={'finished':True,'package':self.package()}
  else:raise ValueError('Unknown tool')
  self.calls.append({'tool':name,'arguments':copy.deepcopy(args),'result':copy.deepcopy(result)})
  (self.folder/'state.json').write_text(json.dumps({'package':self.package(),'charges':self.charges,'fault_attempts':self.fault_attempts,'rejections':self.rejections,'finished':self.finished},ensure_ascii=False,indent=2),encoding='utf-8')
  return result
 def score(self):
  optimum=minimum_cost(self.data,self.case['condition']);checks={'arrived':self.location==self.data['destination'],'deadline':self.time<=self.data['deadline'],'budget':self.cost<=self.data['budget'],'minimum_cost':self.cost==optimum,'no_duplicate_charges':len({x['route_id'] for x in self.charges})==len(self.charges) and sum(x['amount'] for x in self.charges)==self.cost}
  valid=all(checks.values());return {'success':valid and self.finished,'answer_success':valid,'task_completed':self.finished,'checks':checks,'expected_minimum_cost':optimum,'actual_cost':self.cost,'arrival_time':self.time,'location':self.location,'path':[x['route_id'] for x in self.charges],'fault_exposed':self.fault_attempts>0,'permanent_retries':max(0,self.fault_attempts-1) if self.case['condition']=='permanent' else 0,'rejections':self.rejections,'invalid_actions':self.invalid_actions}
 def close(self):pass

def specs():
 definitions=[('get_package','Read package state, virtual clock, budget, all hub names and operation rules.',{},[]),('list_routes','List complete timetable for any origin, including hubs not yet reached. Does not advance time.',{'origin':{'type':'string'}},['origin']),('send_leg','Atomically send via a route_id, waiting for its departure. On failure, no movement or charge. Missed departures cannot be boarded.',{'route_id':{'type':'string'}},['route_id']),('inspect_incident','Read definitive incident status by incident_id returned from dispatch failure.',{'incident_id':{'type':'string'}},['incident_id']),('get_ledger','Read all successful charges and total; failed sends do not appear.',{},[]),('finish','Irreversible final completion; runner stops immediately. Verify package and ledger beforehand. Does not check optimality or correctness.',{},[])]
 return [{'type':'function','function':{'name':n,'description':d,'parameters':{'type':'object','properties':p,'required':req,'additionalProperties':False}}} for n,d,p,req in definitions]
