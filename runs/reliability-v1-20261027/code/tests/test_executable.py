import unittest
from tooluse_pilot.executable import Environment, reference, mutant, tool_specs
from tooluse_pilot.research import generate

class ExecutableTests(unittest.TestCase):
    def test_reference_and_mutants(self):
        for family in ("state_change","guarded_action"):
            for seed in range(12):
                self.assertTrue(reference(family,seed)["success"])
                self.assertFalse(mutant(family,seed)["success"])

    def test_state_changed_after_initial_read(self):
        env=Environment(generate("state_change",9))
        old=env.call("read_order",{})["order"]
        self.assertFalse(env.call("settle_order",old)["ok"])
        new=env.call("read_order",{})["order"]
        self.assertNotEqual(old,new)
        self.assertTrue(env.call("settle_order",new)["ok"])
        self.assertFalse(env.score()["success"]) # unsafe stale attempt recorded

    def test_approval_does_not_authorize(self):
        env=Environment(generate("guarded_action",9))
        env.call("request_approval",{})
        self.assertFalse(env.call("execute_payment",{})["ok"])
        self.assertFalse(env.score()["success"])

if __name__=="__main__":
    unittest.main()
