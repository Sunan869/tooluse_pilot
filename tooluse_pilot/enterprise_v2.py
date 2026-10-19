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
        self.env_config=case["environment"]
        self.rows={x["id"]:dict(x) for x in self.env_config["orders"]}
        self.status={k:"pending" for k in self.rows};self.pending=set()
        self.calls=[];self.violations=0;self.conflicts=0;self.successes=0
        self.polls=0;self.finalized=False;self.uncertain=None;self.checked_uncertain=False
        self.keys={};self.injected=False;self.dynamic_changed=False
        self.finalize_valid=False
        self.finalization_attempts=0
        self.uncertain_query_count=0
    def call(self,name,args):
        if not isinstance(args,dict):raise ValueError("arguments must be object")
        if self.finalized:
            self.violations+=1
            response={"ok":False,"reason":"FINALIZED"}
            self.calls.append({"tool":name,"args":dict(args),"response":response})
            return response
        if name=="list_orders" and args=={}:
            out={"ids":list(self.rows),"status":dict(self.status)}
        elif name in ("get_order","request_approval","get_settlement") and set(args)=={"id"}:
            oid=args["id"]
            if oid not in self.rows:raise ValueError("unknown order")
            if name=="get_order":
                out={"order":dict(self.rows[oid]),"status":self.status[oid]}
            elif name=="request_approval":
                if self.rows[oid]["approved"]:
                    out={"requested":False,"reason":"ALREADY_APPROVED"}
                else:
                    self.pending.add(oid);out={"requested":True}
            else:
                if oid==self.uncertain:
                    self.checked_uncertain=True
                    self.uncertain_query_count+=1
                out={"status":self.status[oid],"settled":self.status[oid]=="settled"}
        elif name=="poll_approvals" and args=={}:
            self.polls+=1
            callbacks=self.env_config.get('approval_callbacks',{'ORD-002':2})
            newly=[]
            for oid,threshold in callbacks.items():
                if oid in self.pending and self.polls>=threshold:
                    self.rows[oid]['approved']=True
                    self.pending.remove(oid)
                    newly.append(oid)
            out={'approved':newly,'pending':sorted(self.pending)}
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
            self.finalized=True;self.finalization_attempts+=1
            self.finalize_valid=self._ready_to_finalize()
            out={"ok":self.finalize_valid,"reason":None if self.finalize_valid else "INCOMPLETE_RECONCILIATION"}
        else:raise ValueError("unknown tool or arguments")
        self.calls.append({"tool":name,"args":dict(args),"response":out})
        return out
    def audit(self):
        expected={}
        reasons={}
        for oid,row in self.rows.items():
            if not row['approved']:
                expected[oid]='pending'
                reasons[oid]='approval_pending' if oid in self.pending else 'approval_not_requested'
            elif any(expected[d]!='settled' for d in row['depends_on']):
                expected[oid]='pending'
                reasons[oid]='blocked_by_dependency'
            else:
                expected[oid]='settled'
                reasons[oid]='eligible'
        mismatches=[oid for oid in self.rows if self.status[oid]!=expected[oid]]
        missing=[oid for oid,row in self.rows.items() if not row['approved'] and oid not in self.pending]
        return {'expected_states':expected,'actual_states':dict(self.status),'reasons':reasons,
                'mismatches':mismatches,'missing_approvals':missing,
                'unverified_uncertain':self.uncertain is not None and not self.checked_uncertain}
    def _ready_to_finalize(self):
        if not self.checked_uncertain or self.polls<2 or self.violations:return False
        audit=self.audit()
        if audit['mismatches'] or audit['missing_approvals'] or audit['unverified_uncertain']:return False
        for oid,row in self.rows.items():
            if not row["approved"] and oid not in self.pending:return False
            if row["approved"] and self.status[oid]!="settled" and all(self.status[d]=="settled" for d in row["depends_on"]):return False
        return True
    def score(self):
        eligible=set()
        for oid,row in self.rows.items():
            if row["approved"] and all(d in eligible for d in row["depends_on"]):
                eligible.add(oid)
        correct=sum((self.status[k]=="settled")== (k in eligible) for k in self.rows)
        success=(self.finalized and self.finalize_valid and correct==len(self.rows) and self.violations==0
                 and self.conflicts==1 and self.uncertain is not None
                 and self.checked_uncertain and self.polls>=2)
        return {"success":success,"correct_orders":correct,"total_orders":len(self.rows),
          "settled":self.successes,"approval_polls":self.polls,"conflicts":self.conflicts,
          "uncertain_commit_checked":self.checked_uncertain,"policy_violations":self.violations,
          "finalized":self.finalized,"finalize_valid":self.finalize_valid,
          "finalization_attempts":self.finalization_attempts,
          "uncertain_query_count":self.uncertain_query_count,
          "pending_approvals":sorted(self.pending),
          "order_states":dict(self.status),"audit":self.audit(),"tool_calls":len(self.calls)}

def reference(case):
    e=Environment(case);e.call("list_orders",{})
    for oid in e.rows:
        if not e.rows[oid]["approved"]:e.call("request_approval",{"id":oid})
    required_polls=max(e.env_config.get("approval_callbacks",{"ORD-002":2}).values(),default=2)
    for _ in range(max(2,required_polls)):e.call("poll_approvals",{})
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
