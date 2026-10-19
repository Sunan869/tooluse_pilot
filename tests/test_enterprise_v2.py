import unittest
from tooluse_pilot.enterprise_v2 import generate,Environment,reference,mutant
class EnterpriseV2Tests(unittest.TestCase):
    def test_reference_and_mutants(self):
        for seed in range(15):
            c=generate(seed,8)
            self.assertTrue(reference(c)["success"],(seed,reference(c)))
            self.assertFalse(mutant(c)["success"])
    def test_response_lost_requires_readback(self):
        e=Environment(generate(0,8));e.call("request_approval",{"id":"ORD-002"})
        e.call("poll_approvals",{});e.call("poll_approvals",{})
        r=e.call("get_order",{"id":"ORD-001"})["order"]
        self.assertEqual(e.call("settle",{"id":"ORD-001","version":r["version"],"key":"x"})["reason"],"VERSION_CONFLICT")
        r=e.call("get_order",{"id":"ORD-001"})["order"]
        self.assertEqual(e.call("settle",{"id":"ORD-001","version":r["version"],"key":"x"})["reason"],"RESPONSE_LOST")
        self.assertFalse(e.score()["uncertain_commit_checked"])
        self.assertTrue(e.call("get_settlement",{"id":"ORD-001"})["settled"])
