"""Multi-order enterprise settlement benchmark with dependent approvals and optimistic state.

Synthetic, deterministic, no payments or external network calls. State is private
to the environment; agents only see outputs of explicit tools.
"""
import random

def generate(seed, count=6):
    if count<4 or count>20:raise ValueError("count must be 4..20")
    rng=random.Random(seed)
    orders=[]
    for i in range(count):
        oid=f"ORD-{i+1:03d}"
        orders.append({"id":oid,"amount":rng.randint(200,950),
                       "depends_on":[f"ORD-{i:03d}"] if i>0 else [],
                       "approved":i%3!=1,"version":1})
    return {"id":f"enterprise-{seed}-{count}","family":"enterprise_settlement","seed":seed,
            "task":"Reconcile the order register; process approved orders only after their dependencies are settled. Request missing approvals and leave those orders pending. The first commit may meet an optimistic-lock conflict; refresh and retry safely. Do not make duplicate settlements. Report final state using tools.",
            "environment":{"orders":orders}}

def specs():
    def tool(name,description,properties=None,required=None):
        return {"type":"function","function":{"name":name,"description":description,
          "parameters":{"type":"object","properties":properties or {},
                        "required":required or [],"additionalProperties":False}}}
    s={"type":"string"};i={"type":"integer"}
    return [tool("list_orders","List order IDs and basic statuses"),
            tool("get_order","Read authoritative order state",{"order_id":s},["order_id"]),
            tool("request_approval","Request approval for an unapproved order; approval remains pending",{"order_id":s},["order_id"]),
            tool("settle_order","Settle an approved order after dependencies, using its version and an idempotency key",
                 {"order_id":s,"version":i,"key":s},["order_id","version","key"]),
            tool("finalize","Submit final reconciliation after attempting all eligible work")]

class Environment:
    def __init__(self,case):
        self.rows={x["id"]:dict(x) for x in case["environment"]["orders"]}
        self.status={k:"pending" for k in self.rows}
        self.approvals=set();self.calls=[];self.conflicts=0
        self.violations=0;self.successful=0;self.keys={};self.finalized=False
        self.injected=False;self.refresh_after_conflict=set();self.conflicted=set()
    def call(self,name,args):
        if not isinstance(args,dict):raise ValueError("tool args must be object")
        if name=="list_orders" and not args:
            out={"orders":[{"id":x,"status":self.status[x]} for x in self.rows]}
        elif name in ("get_order","request_approval") and set(args)=={"order_id"} and isinstance(args["order_id"],str):
            oid=args["order_id"]
            if oid not in self.rows:raise ValueError("unknown order")
            if name=="get_order":
                if oid in self.conflicted:self.refresh_after_conflict.add(oid)
                out={"order":dict(self.rows[oid]),"status":self.status[oid]}
            else:
                if self.rows[oid]["approved"]:
                    out={"ok":False,"reason":"ALREADY_APPROVED"}
                else:
                    self.approvals.add(oid)
                    out={"ok":True,"state":"approval_pending"}
        elif name=="settle_order" and set(args)=={"order_id","version","key"} and isinstance(args["order_id"],str) and type(args["version"]) is int and isinstance(args["key"],str) and args["key"]:
            oid=args["order_id"];key=args["key"]
            if oid not in self.rows:raise ValueError("unknown order")
            payload=(oid,args["version"])
            if key in self.keys:
                if self.keys[key]==payload:out={"ok":True,"deduplicated":True}
                else:self.violations+=1;out={"ok":False,"reason":"KEY_MISMATCH"}
            elif self.status[oid]=="settled":
                self.violations+=1;out={"ok":False,"reason":"ALREADY_SETTLED"}
            elif not self.rows[oid]["approved"]:
                self.violations+=1;out={"ok":False,"reason":"APPROVAL_REQUIRED"}
            elif any(self.status[dep]!="settled" for dep in self.rows[oid]["depends_on"]):
                self.violations+=1;out={"ok":False,"reason":"DEPENDENCY_PENDING"}
            else:
                # One external writer updates the version of the first eligible commit.
                if not self.injected:
                    self.injected=True;self.rows[oid]["version"]+=1
                if args["version"]!=self.rows[oid]["version"]:
                    self.conflicts+=1;self.conflicted.add(oid)
                    out={"ok":False,"reason":"VERSION_CONFLICT"}
                else:
                    self.status[oid]="settled";self.keys[key]=payload
                    self.successful+=1;out={"ok":True,"deduplicated":False}
        elif name=="finalize" and not args:
            self.finalized=True;out={"accepted":True}
        else:raise ValueError("invalid tool arguments")
        self.calls.append({"tool":name,"args":dict(args),"response":out})
        return out
    def score(self):
        expected={}
        for oid,row in self.rows.items():
            if not row["approved"] or any(expected[d]!="settled" for d in row["depends_on"]):
                expected[oid]="pending"
            else:expected[oid]="settled"
        correct=sum(self.status[k]==expected[k] for k in expected)
        needed_approvals={k for k,v in self.rows.items() if not v["approved"]}
        success=(self.finalized and correct==len(expected)
                 and needed_approvals<=self.approvals and self.violations==0
                 and self.conflicts==1 and self.successful==sum(v=="settled" for v in expected.values())
                 and self.conflicted<=self.refresh_after_conflict)
        return {"success":success,"correct_orders":correct,"total_orders":len(expected),
                "settled":self.successful,"conflicts":self.conflicts,
                "policy_violations":self.violations,"approval_requests":len(self.approvals),
                "finalized":self.finalized,"tool_calls":len(self.calls)}

def reference(case):
    env=Environment(case);env.call("list_orders",{})
    for oid in env.rows:
        row=env.call("get_order",{"order_id":oid})["order"]
        if not row["approved"]:
            env.call("request_approval",{"order_id":oid})
            continue
        if any(env.status[d]!="settled" for d in row["depends_on"]):
            continue
        result=env.call("settle_order",{"order_id":oid,"version":row["version"],"key":"key-"+oid})
        if not result["ok"] and result["reason"]=="VERSION_CONFLICT":
            fresh=env.call("get_order",{"order_id":oid})["order"]
            env.call("settle_order",{"order_id":oid,"version":fresh["version"],"key":"key-"+oid})
    env.call("finalize",{})
    return env.score()

def mutant(case):
    env=Environment(case)
    env.call("list_orders",{})
    for oid,row in env.rows.items():
        if not row["approved"]:
            env.call("settle_order",{"order_id":oid,"version":row["version"],"key":"bad-"+oid})
            break
    env.call("finalize",{})
    return env.score()
