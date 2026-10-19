import unittest
from tooluse_pilot.enterprise_v2 import generate,Environment,reference,mutant
class EnterpriseV2Tests(unittest.TestCase):
    def test_reference_and_mutants(self):
        for seed in range(15):
            c=generate(seed,8)
            self.assertTrue(reference(c)["success"],(seed,reference(c)))
            self.assertFalse(mutant(c)["success"])
    def test_duplicate_after_lost_response_does_not_charge_twice(self):
        e=Environment(generate(4,8))
        e.call("get_order",{"id":"ORD-001"})
        a=e.call("settle",{"id":"ORD-001","version":1,"key":"k1"})
        self.assertEqual(a["reason"],"VERSION_CONFLICT")
        fresh=e.call("get_order",{"id":"ORD-001"})["order"]
        b=e.call("settle",{"id":"ORD-001","version":fresh["version"],"key":"k1"})
        self.assertEqual(b["reason"],"RESPONSE_LOST")
        self.assertEqual(e.successes,1)
        replay=e.call("settle",{"id":"ORD-001","version":fresh["version"],"key":"k1"})
        self.assertTrue(replay["deduplicated"])
        self.assertEqual(e.successes,1)
        self.assertFalse(e.checked_uncertain)
        e.call("get_settlement",{"id":"ORD-001"})
        self.assertTrue(e.checked_uncertain)
        illegal=e.call("settle",{"id":"ORD-001","version":fresh["version"],"key":"other-key"})
        self.assertFalse(illegal["ok"])
        self.assertGreater(e.violations,0)

    def test_approval_does_not_automatically_grant(self):
        e=Environment(generate(2,8))
        e.call("request_approval",{"id":"ORD-002"})
        self.assertFalse(e.rows["ORD-002"]["approved"])
        e.call("poll_approvals",{})
        self.assertFalse(e.rows["ORD-002"]["approved"])
        e.call("poll_approvals",{})
        self.assertTrue(e.rows["ORD-002"]["approved"])

    def test_early_finalize_is_not_success(self):
        e=Environment(generate(0,8))
        response=e.call("finalize",{})
        self.assertFalse(response["ok"])
        self.assertEqual(response["reason"],"INCOMPLETE_RECONCILIATION")
        self.assertFalse(e.score()["success"])
        late=e.call("get_order",{"id":"ORD-001"})
        self.assertEqual(late["reason"],"FINALIZED")
        self.assertEqual(e.score()["policy_violations"],1)

    def test_reference_has_valid_finalize(self):
        self.assertTrue(reference(generate(1,8))["success"])

    def test_response_lost_requires_readback(self):
        e=Environment(generate(0,8));e.call("request_approval",{"id":"ORD-002"})
        e.call("poll_approvals",{});e.call("poll_approvals",{})
        r=e.call("get_order",{"id":"ORD-001"})["order"]
        self.assertEqual(e.call("settle",{"id":"ORD-001","version":r["version"],"key":"x"})["reason"],"VERSION_CONFLICT")
        r=e.call("get_order",{"id":"ORD-001"})["order"]
        self.assertEqual(e.call("settle",{"id":"ORD-001","version":r["version"],"key":"x"})["reason"],"RESPONSE_LOST")
        self.assertFalse(e.score()["uncertain_commit_checked"])
        self.assertTrue(e.call("get_settlement",{"id":"ORD-001"})["settled"])
