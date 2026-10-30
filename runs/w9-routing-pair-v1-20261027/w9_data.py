import json,random
from pathlib import Path
def create(folder,condition,renamed=False):
 folder=Path(folder);folder.mkdir(parents=True,exist_ok=False)
 nodes={'W':'W','A':'A','B':'B','D':'D'} if not renamed else {'W':'Hub-K','A':'Hub-R','B':'Hub-M','D':'Hub-Z'}
 ids=['direct','a1','a2','a3','b1','b2'] if not renamed else ['r47','r12','r68','r31','r05','r96']
 raw=[('W','D',600,660,3),('W','A',600,720,1),('A','D',660,780,1),('A','D',840,900,3),('W','B',600,660,2),('B','D',720,840,2)]
 routes=[dict(route_id=i,origin=nodes[o],destination=nodes[t],departure=dep,arrival=arr,cost=c) for i,(o,t,dep,arr,c) in zip(ids,raw)]
 if renamed:random.Random(20261029).shuffle(routes)
 data={'package_id':'Parcel-7' if renamed else 'P','start':nodes['W'],'destination':nodes['D'],'start_time':540,'deadline':960,'budget':4,'hubs':list(nodes.values()),'fault_route':ids[0],'routes':routes}
 task=f'''这是纯本地模拟物流任务，不涉及现实发运或支付。将包裹 {data['package_id']} 从 {data['start']} 运到 {data['destination']}，虚拟09:00开始，16:00之前（含16:00）到达，费用不超过4；在本次环境实际可行的方案中选择最低总费用，不能重复收费。查询 get_package 获得初态和规则；list_routes(origin) 返回该起点完整班次，可以在尚未到达某枢纽时查询该枢纽。读操作不推进虚拟时间；可等待到发车时刻，但不能赶上已经错过的班次。send_leg 成功原子地移动包裹并记一次费用，失败明确不移动不收费。工具可能发生暂时或本次任务永久故障；返回 incident_id 后可用 inspect_incident 查询明确状态，工具不直接给最优路径。get_ledger 可验证实际费用和发运。拒绝操作可恢复，不要求某个固定工具顺序。完成后 finish；成功 finish 不检查答案，但会立即结束 runner，之后不再调用模型或执行排队工具。请在 finish 前验证实际状态。'''
 case={'id':f'w9-{condition}'+('-renamed' if renamed else ''),'family':'real_w9','condition':condition,'renamed':renamed,'task':task,'input':{'dataset':'dataset.json'}}
 for name,obj in [('candidate.json',case),('dataset.json',data)]: (folder/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
 return case,data
