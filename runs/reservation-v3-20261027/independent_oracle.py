"""Independent list-based reservation simulator; no production imports."""
def independent(w):
    def table(s):
        rows=list(w[s].values);return [dict(zip(rows[0],r)) for r in rows[1:]]
    orders=table('Orders');policy=dict(list(w['Policy'].values)[1:]);limits=dict(list(w['Limits'].values)[1:])
    quantities=dict(list(w['Corrections'].values)[1:]);ranks=dict(list(w['Priority'].values)[1:])
    previous=dict(list(w['Commitments'].values)[1:]);withdrawn={r[0] for r in list(w['Withdrawn'].values)[1:]}
    edges=list(w['Dependencies'].values)[1:];blocked=set(withdrawn)
    # Missing previous parents also break a previous commitment.
    for child,parent in edges:
        if child in previous and parent not in previous:blocked.add(child)
    queue=list(blocked)
    while queue:
        parent=queue.pop(0)
        for child,p in edges:
            if p==parent and child in previous and child not in blocked:blocked.add(child);queue.append(child)
    retained={n:a for n,a in previous.items() if n not in blocked}
    byid={o['ID']:o for o in orders}
    selected=[(n,a,byid[n]['Group']) for n,a in retained.items()];decisions=[]
    for o in sorted(orders,key=lambda o:(-ranks[o['ID']],o['ID'])):
        n=o['ID'];amount=retained.get(n,o['Price']*quantities.get(n,o['Qty']))
        if n in retained:reason='retained'
        else:
            bad=[('cancelled',n in withdrawn),('inactive',o['Status']!='active'),('city',any(o[c]!=1 for c in policy['Cities'].split(','))),('per_order',amount>policy['Max per order']),('dependency',any(p not in [v[0] for v in selected] for child,p in edges if child==n)),('group_cap',sum(v[1] for v in selected if v[2]==o['Group'])+amount>limits[o['Group']]),('budget',sum(v[1] for v in selected)+amount>policy['Budget'])]
            reason=next((label for label,test in bad if test),'selected')
            if reason=='selected':selected.append((n,amount,o['Group']))
        decisions.append([n,amount,int(reason in ['selected','retained']),reason])
    best=sorted(selected,key=lambda x:(-x[1],x[0]))[0] if selected else ('NONE',0,None)
    return list(map(str,[sum(x[1] for x in selected),len(selected),best[0],best[1]])),decisions
