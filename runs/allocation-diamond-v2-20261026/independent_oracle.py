"""Independent allocation oracle; no model calls or filesystem writes."""
def independent(w):
    tables={s:[dict(zip(next(w[s].values),row)) for row in list(w[s].values)[1:]] for s in ['Orders','Corrections','Priority','Dependencies']}
    policy=dict(list(w['Policy'].values)[1:]);limits=dict(list(w['Limits'].values)[1:])
    selected=[];decisions=[]
    rank={x['ID']:x['Rank'] for x in tables['Priority']}
    corrections={x['ID']:x['Quantity'] for x in tables['Corrections']}
    for order in sorted(tables['Orders'],key=lambda x:(-rank[x['ID']],x['ID'])):
        n=order['ID'];amount=order['Price']*corrections.get(n,order['Qty'])
        parents=[x['Requires'] for x in tables['Dependencies'] if x['ID']==n]
        tests=[('inactive',order['Status']!='active'),('city',any(order[c]!=1 for c in policy['Cities'].split(','))),('per_order',amount>policy['Max per order']),('dependency',not set(parents).issubset(x[0] for x in selected)),('group_cap',sum(x[1] for x in selected if x[2]==order['Group'])+amount>limits[order['Group']]),('budget',sum(x[1] for x in selected)+amount>policy['Budget'])]
        reason=next((reason for reason,bad in tests if bad),'selected')
        if reason=='selected':selected.append((n,amount,order['Group']))
        decisions.append([n,amount,int(reason=='selected'),reason])
    best=sorted(selected,key=lambda x:(-x[1],x[0]))[0] if selected else ('NONE',0,None)
    return list(map(str,[sum(x[1] for x in selected),len(selected),best[0],best[1]])),decisions
