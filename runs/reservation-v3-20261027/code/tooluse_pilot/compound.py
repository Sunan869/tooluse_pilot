"""Deterministic multi-source optimistic settlement and idempotency benchmark."""
import random

def generate(seed):
    rng=random.Random(seed);amount=rng.randint(500,9000)
    return {"family":"compound_settlement","id":f"compound_settlement-{seed}","seed":seed,
      "task":"Compare reporting replica with authoritative order before settlement. An external writer can race settlement. Recover a version conflict, settle exactly once, and avoid duplicate charges.",
      "environment":{"replica":{"version":1,"amount":amount},
        "initial_primary":{"version":2,"amount":amount+73},
        "raced_primary":{"version":3,"amount":amount+114}}}

def specs():
    def f(n,desc,props=None,req=None):
        return {"type":"function","function":{"name":n,"description":desc,
          "parameters":{"type":"object","properties":props or {},"required":req or [],
                        "additionalProperties":False}}}
    return [f("read_replica","Read possibly delayed reporting data"),
            f("read_primary","Read authoritative order"),
            f("settle","Settle once with version, amount and idempotency key",
              {"version":{"type":"integer"},"amount":{"type":"integer"},"key":{"type":"string"}},
              ["version","amount","key"])]

class CompoundEnvironment:
    def __init__(self,case):
        self.env=case["environment"];self.primary=dict(self.env["initial_primary"])
        self.calls=[];self.replica_seen=False;self.primary_seen=False
        self.preflight=False;self.attempted=False;self.raced=False
        self.conflicts=0;self.violations=0;self.successes=0
        self.commits={};self.settled=None;self.recovered=False
    def call(self,name,args):
        if not isinstance(args,dict):raise ValueError("arguments must be object")
        if name=="read_replica" and args=={}:
            self.replica_seen=True;out={"order":dict(self.env["replica"]),"source":"replica"}
        elif name=="read_primary" and args=={}:
            self.primary_seen=True
            if self.replica_seen and not self.attempted and self.primary["version"]!=self.env["replica"]["version"]:
                self.preflight=True
            out={"order":dict(self.primary),"source":"primary"}
        elif name=="settle" and set(args)=={"version","amount","key"} and type(args["version"]) is int and type(args["amount"]) is int and isinstance(args["key"],str) and args["key"]:
            self.attempted=True
            if not self.raced:
                self.primary=dict(self.env["raced_primary"]);self.raced=True
            key=args["key"];payload=(args["version"],args["amount"])
            if key in self.commits:
                if self.commits[key]==payload:
                    out={"ok":True,"deduplicated":True}
                else:
                    self.violations+=1;out={"ok":False,"reason":"KEY_PAYLOAD_CONFLICT"}
            elif self.settled is not None:
                self.violations+=1;out={"ok":False,"reason":"ALREADY_SETTLED"}
            elif payload!=(self.primary["version"],self.primary["amount"]):
                self.conflicts+=1;out={"ok":False,"reason":"VERSION_CONFLICT"}
            else:
                self.successes+=1;self.settled={"version":payload[0],"amount":payload[1]}
                self.commits[key]=payload;self.recovered=(self.conflicts==1)
                out={"ok":True,"deduplicated":False}
        else:raise ValueError("invalid tool or arguments")
        self.calls.append({"tool":name,"args":dict(args),"response":out})
        return out
    def score(self):
        return {"success":self.preflight and self.successes==1 and self.conflicts==1 and
                    self.violations==0 and self.recovered and self.settled==self.env["raced_primary"],
                "preflight_evidence":self.preflight,"recoverable_conflicts":self.conflicts,
                "policy_violations":self.violations,"successful_settlements":self.successes,
                "settled":self.settled,"tool_calls":len(self.calls)}

def reference(case):
    e=CompoundEnvironment(case)
    e.call("read_replica",{})
    old=e.call("read_primary",{})["order"]
    e.call("settle",{"version":old["version"],"amount":old["amount"],"key":"job-1"})
    latest=e.call("read_primary",{})["order"]
    e.call("settle",{"version":latest["version"],"amount":latest["amount"],"key":"job-1"})
    return e.score()

def mutant(case):
    e=CompoundEnvironment(case)
    old=e.call("read_primary",{})["order"]
    e.call("settle",{"version":old["version"],"amount":old["amount"],"key":"job-1"})
    return e.score()
