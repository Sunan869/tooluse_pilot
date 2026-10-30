"""Advanced deterministic state consistency environments."""
from .research import generate
from .executable import Environment

PROFILES=("implicit","multi_source","concurrent")

class StateProfile(Environment):
    def __init__(self, seed, profile):
        if profile not in PROFILES: raise ValueError("invalid profile")
        self.profile=profile
        case = seed if isinstance(seed,dict) else generate("state_change",seed)
        super().__init__(case)
        self.conflicts=0
        self.second_update=False
        self.authoritative_reads=0
        self.replica_reads=0
        self.successful_settlements=0
        self.policy_violations=0
        self.recovery_events=[]
        self.pre_settlement_evidence=False
        self.settlement_attempted=False

    def call(self,name,args):
        if name=="read_replica":
            if args != {}: raise ValueError("read_replica expects empty arguments")
            self.replica_reads+=1
            response={"order":{"version":self.state["initial_version"],"amount":self.state["initial_amount"]},"source":"replica"}
            self.calls.append({"tool":name,"args":dict(args),"response":response})
            return response
        if name=="read_order":
            self.authoritative_reads+=1
            response=super().call(name,args)
            if self.profile!="baseline":response.pop("notice",None)
            if self.profile=="multi_source" and self.replica_reads and not self.settlement_attempted and response["order"]["version"]!=self.state["initial_version"]:
                self.pre_settlement_evidence=True
            return response
        if name=="settle_order": self.settlement_attempted=True
        if name=="settle_order" and self.settled:
            self.policy_violations+=1
            response={"ok":False,"reason":"ALREADY_SETTLED"}
            self.calls.append({"tool":name,"args":dict(args),"response":response})
            return response
        if name=="settle_order" and self.profile=="concurrent" and not self.second_update and self.first_read:
            self.second_update=True
            self.state["current_version"]+=1
            self.state["current_amount"]+=41
            self.external_updates+=1
        response=super().call(name,args)
        if name=="settle_order" and response["ok"]:
            self.successful_settlements+=1
        if name=="settle_order" and not response["ok"]:
            self.conflicts+=1
            self.recovery_events.append({"kind":"optimistic_conflict","attempt":self.conflicts})
            # A rejected optimistic lock is recoverable, not a policy violation.
            if self.invalid_actions>0:self.invalid_actions-=1
            if self.conflicts>1:
                self.policy_violations+=1
        return response

    def score(self):
        result=super().score()
        need=2 if self.profile=="concurrent" else 1
        sources_ok = self.profile!="multi_source" or self.pre_settlement_evidence
        result["success"]=(self.settled and self.invalid_actions==0 and self.external_updates==need
                           and self.conflicts<=1 and self.authoritative_reads>=2
                           and self.successful_settlements==1 and sources_ok and self.policy_violations==0)
        result["profile"]=self.profile
        result["conflicts"]=self.conflicts
        result["authoritative_reads"]=self.authoritative_reads
        result["replica_reads"]=self.replica_reads
        result["pre_settlement_evidence"]=self.pre_settlement_evidence
        result["successful_settlements"]=self.successful_settlements
        result["policy_violations"]=self.policy_violations
        result["recovery_events"]=list(self.recovery_events)
        return result

def reference(profile,seed):
    env=StateProfile(seed,profile)
    if profile=="multi_source": env.call("read_replica",{})
    env.call("read_order",{})
    current=env.call("read_order",{})["order"]
    if not env.call("settle_order",current)["ok"]:
        fresh=env.call("read_order",{})["order"]
        env.call("settle_order",fresh)
    return env.score()

def mutant(profile,seed):
    env=StateProfile(seed,profile)
    stale=env.call("read_replica",{})["order"]
    env.call("settle_order",stale)
    return env.score()
