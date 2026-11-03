import itertools
def oracle(data,condition):
 routes=[r for r in data['routes'] if condition!='permanent' or r['route_id']!=data['fault_route']];solutions=[]
 for length in range(1,len(routes)+1):
  for route in itertools.permutations(routes,length):
   location=data['start'];clock=data['start_time'];cost=0;valid=True
   for leg in route:
    if leg['origin']!=location or leg['departure']<clock:valid=False;break
    location=leg['destination'];clock=leg['arrival'];cost+=leg['cost']
   if valid and location==data['destination'] and clock<=data['deadline'] and cost<=data['budget']:solutions.append({'path':[r['route_id'] for r in route],'arrival':clock,'cost':cost})
 minimum=min(s['cost'] for s in solutions)
 return {'minimum_cost':minimum,'optimal_paths':[s for s in solutions if s['cost']==minimum],'all_feasible_paths':solutions}
