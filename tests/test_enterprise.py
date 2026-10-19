import unittest
from tooluse_pilot.enterprise import generate,Environment,reference,mutant
class EnterpriseTests(unittest.TestCase):
    def test_reference_mutant(self):
        for seed in range(20):
            case=generate(seed,8)
            self.assertTrue(reference(case)["success"],(seed,reference(case)))
            self.assertFalse(mutant(case)["success"])
    def test_independent_and_blocked_branches(self):
        score=reference(generate(7,8))
        self.assertTrue(score["success"])
        self.assertGreaterEqual(score["executable_orders"],3)
        self.assertGreaterEqual(score["blocked_orders"],2)
        self.assertEqual(score["correct_orders"],8)

    def test_dependency_and_duplicate(self):
        e=Environment(generate(3,6))
        row=e.call("get_order",{"order_id":"ORD-003"})["order"]
        self.assertFalse(e.call("settle_order",{"order_id":"ORD-003","version":row["version"],"key":"wrong"})["ok"])
        self.assertGreater(e.score()["policy_violations"],0)
