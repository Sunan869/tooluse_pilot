"""Advanced deterministic state consistency environments."""
from .research import generate
from .executable import Environment

PROFILES=("implicit","multi_source","concurrent")

class StateProfile(Environment):
    def __init__(self, seed, profile):
        if profile not in PROFILES: raise ValueError("invalid profile")
        self.profile=profile
        super().__init__(generate("state_change",seed))
        self.conflicts=0
        self.second_update=False

    def call(self,name,args):
        if name=="read_replica":
            response={"order":{"version":self.state["initial_version"],"amount":self.state["initial_amount"]},"source":"replica"}
            self.calls.append({"tool":name,"args":dict(args),"response":response})
            return response
        if name=="read_order":
            response=super().call(name,args)
            if self.profile!="baseline":response.pop("notice",None)
            return response
        if name=="settle_order" and self.profile=="concurrent" and not self.second_update and self.first_read:
            self.second_update=True
            self.state["current_version"]+=1
            self.state["current_amount"]+=41
            self.external_updates+=1
        response=super().call(name,args)
        if name=="settle_order" and not response["ok"]:
            self.conflicts+=1
            # A bounded optimistic-lock conflict can be recovered safely.
            if self.invalid_actions>0:self.invalid_actions-=1
        return response

    def score(self):
        result=super().score()
        need=2 if self.profile=="concurrent" else 1
        result["success"]=self.settled and self.invalid_actions==0 and self.external_updates==need and self.conflicts<=1
        result["profile"]=self.profile
        result["conflicts"]=self.conflicts
        return result

def reference(profile,seed):
    env=StateProfile(seed,profile)
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
