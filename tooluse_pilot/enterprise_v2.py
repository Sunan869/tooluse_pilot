"""Enterprise settlement v2: deterministic async approvals, DAG and uncertain commit."""
import random

def generate(seed, count=8):
    if count<6 or count>20: raise ValueError("count 6..20")
    rng=random.Random(seed)
    orders=[]
    for i in range(count):
        oid=f"ORD-{i+1:03d}"
        deps=([f"ORD-{i-1:03d}"] if i>1 else [])
        if i>=4 and i%2==0: deps.append("ORD-001")
        orders.append({"id":oid,"amount":rng.randint(100,1000),"depends_on":sorted(set(deps)),
                       "approved":i%3!=1,"version":1})
    return {"id":f"enterprise_v2-{seed}-{count}","family":"enterprise_settlement_v2",
       "seed":seed,"task":"Process the order DAG safely. Request outstanding approvals and poll them; settle only eligible orders. Settlement may report a timeout although committed: check status before deciding whether to retry. Versions may change; re-read on conflicts. Finalize only after all possible orders are handled.",
       "environment":{"orders":orders}}

def specs():
    def fn(n,d,p=None,r=None):
        return {"type":"function","function":{"name":n,"description":d,
          "parameters":{"type":"object","properties":p or {},"required":r or [],"additionalProperties":False}}}
    s={"type":"string"};i={"type":"integer"}
    return [fn("list_orders","List identifiers and current settlement states"),
      fn("get_order","Get order version, approval and dependencies",{"id":s},["id"]),
      fn("request_approval","Request pending approval",{"id":s},["id"]),
      fn("poll_approvals","Poll pending approvals; external decisions may arrive"),
      fn("settle","Perform idempotent settlement; a timeout may conceal success",
         {"id":s,"version":i,"key":s},["id","version","key"]),
      fn("get_settlement","Check server-side settlement outcome",{"id":s},["id"]),
      fn("finalize","Finalize audited reconciliation")]

class Environment:
    def __init__(self,case):
        self.rows={x["id"]:dict(x) for x in case["environment"]["orders"]}
        self.status={k:"pending" for k in self.rows};self.pending=set()
        self.calls=[];self.violations=0;self.conflicts=0;self.successes=0
        self.polls=0;self.finalized=False;self.uncertain=None;self.checked_uncertain=False
        self.keys={};self.injected=False;self.dynamic_changed=False
    def call(self,name,args):
        if not isinstance(args,dict):raise ValueError("arguments must be object")
        if name=="list_orders" and args=={}:
            out={"ids":list(self.rows),"status":dict(self.status)}
        elif name in ("get_order","request_approval","get_settlement") and set(args)=={"id"}:
            oid=args["id"]
            if oid not in self.rows:raise ValueError("unknown order")
            if name=="get_order":
                out={"order":dict(self.rows[oid]),"status":self.status[oid]}
            elif name=="request_approval":
                self.pending.add(oid);out={"requested":True}
            else:
                if oid==self.uncertain:self.checked_uncertain=True
                out={"status":self.status[oid],"settled":self.status[oid]=="settled"}
        elif name=="poll_approvals" and args=={}:
            self.polls+=1
            # Deterministic asynchronous callback, approval for ORD-002 unlocks its branch.
            oid="ORD-002"
            if oid in self.pending and self.polls>=2:
                self.rows[oid]["approved"]=True;self.pending.remove(oid)
            out={"approved":[oid] if self.rows.get(oid,{}).get("approved") else [],
                 "pending":sorted(self.pending)}
        elif name=="settle" and set(args)=={"id","version","key"}:
            oid=args["id"];key=args["key"];version=args["version"]
            if oid not in self.rows or type(version) is not int or not isinstance(key,str) or not key:
                raise ValueError("invalid settlement arguments")
            row=self.rows[oid]
            if key in self.keys:
                if self.keys[key]==(oid,version):out={"ok":True,"deduplicated":True}
                else:self.violations+=1;out={"ok":False,"reason":"KEY_CONFLICT"}
            elif self.status[oid]=="settled":
                self.violations+=1;out={"ok":False,"reason":"ALREADY_SETTLED"}
            elif not row["approved"] or any(self.status[d]!="settled" for d in row["depends_on"]):
                self.violations+=1;out={"ok":False,"reason":"PREREQUISITE_FAILED"}
            else:
                if not self.injected:
                    self.injected=True;row["version"]+=1;self.dynamic_changed=True
                if version!=row["version"]:
                    self.conflicts+=1;out={"ok":False,"reason":"VERSION_CONFLICT"}
                else:
                    self.status[oid]="settled";self.keys[key]=(oid,version);self.successes+=1
                    if self.uncertain is None:
                        self.uncertain=oid;out={"ok":False,"reason":"RESPONSE_LOST","outcome":"unknown"}
                    else:out={"ok":True}
        elif name=="finalize" and args=={}:
            self.finalized=True;out={"ok":True}
        else:raise ValueError("unknown tool or arguments")
        self.calls.append({"tool":name,"args":dict(args),"response":out})
        return out
    def score(self):
        eligible=set()
        for oid,row in self.rows.items():
            if row["approved"] and all(d in eligible for d in row["depends_on"]):
                eligible.add(oid)
        correct=sum((self.status[k]=="settled")== (k in eligible) for k in self.rows)
        success=(self.finalized and correct==len(self.rows) and self.violations==0
                 and self.conflicts==1 and self.uncertain is not None
                 and self.checked_uncertain and self.polls>=2)
        return {"success":success,"correct_orders":correct,"total_orders":len(self.rows),
          "settled":self.successes,"approval_polls":self.polls,"conflicts":self.conflicts,
          "uncertain_commit_checked":self.checked_uncertain,"policy_violations":self.violations,
          "finalized":self.finalized,"tool_calls":len(self.calls)}

def reference(case):
    e=Environment(case);e.call("list_orders",{})
    for oid in e.rows:
        if not e.rows[oid]["approved"]:e.call("request_approval",{"id":oid})
    e.call("poll_approvals",{});e.call("poll_approvals",{})
    for oid in e.rows:
        r=e.call("get_order",{"id":oid})["order"]
        if not r["approved"] or any(e.status[d]!="settled" for d in r["depends_on"]):continue
        out=e.call("settle",{"id":oid,"version":r["version"],"key":"job-"+oid})
        if out.get("reason")=="VERSION_CONFLICT":
            r=e.call("get_order",{"id":oid})["order"]
            out=e.call("settle",{"id":oid,"version":r["version"],"key":"job-"+oid})
        if out.get("reason")=="RESPONSE_LOST":e.call("get_settlement",{"id":oid})
    e.call("finalize",{})
    return e.score()

def mutant(case):
    e=Environment(case);e.call("list_orders",{})
    e.call("finalize",{})
    return e.score()
