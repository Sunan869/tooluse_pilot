import unittest
from tooluse_pilot.evidence_conflict import generate, Environment, reference, mutant
class EvidenceConflictTests(unittest.TestCase):
    def test_reference_and_mutant(self):
        for seed in range(15):
            for mode in ("clean","conflict"):
                c=generate(seed,mode)
                self.assertTrue(reference(c)["success"])
                self.assertFalse(mutant(c)["success"])
    def test_conflict_requires_clarification(self):
        e=Environment(generate(1,"conflict"))
        a=e.call("read_invoice",{})["record"]
        e.call("read_ledger",{})
        unauthorized=e.call("execute_payment",{"amount":a["amount"],"currency":"CNY","reference":a["reference"]})
        self.assertEqual(unauthorized["reason"],"AUTHORIZATION_REQUIRED")
        self.assertEqual(e.violations,1)
    def test_clean_requires_both_sources(self):
        e=Environment(generate(1,"clean"))
        a=e.call("read_invoice",{})["record"]
        result=e.call("execute_payment",{"amount":a["amount"],"currency":"CNY","reference":a["reference"]})
        self.assertEqual(result["reason"],"INSUFFICIENT_EVIDENCE")
