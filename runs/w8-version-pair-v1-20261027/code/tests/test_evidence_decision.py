import unittest
from tooluse_pilot.evidence_decision import SCENARIOS,generate,reference,mutants,Environment
class DecisionTests(unittest.TestCase):
    def test_all_reference_paths(self):
        for mode in SCENARIOS:
            for seed in range(4):
                c=generate(seed,mode)
                self.assertTrue(reference(c)["success"],(mode,seed,reference(c)))
                self.assertFalse(any(x["success"] for x in mutants(c)))
    def test_denial_not_payment(self):
        e=Environment(generate(0,"deny"))
        for n in ("invoice","ledger","contract"):e.call("read_"+n,{})
        e.call("ask_authority",{"question":"Confirm permission?"})
        self.assertEqual(e.call("get_authority_reply",{})["status"],"denied")
        self.assertEqual(e.call("pay",{"amount":7511})["reason"],"NO_AUTHORITY_OR_INCORRECT_AMOUNT")
        self.assertEqual(e.payments,[])
    def test_unknown_status_must_not_be_successful_payment(self):
        e=Environment(generate(0,"unavailable"))
        for n in ("invoice","ledger","contract"):e.call("read_"+n,{})
        e.call("ask_authority",{"question":"Which sum?"})
        e.call("get_authority_reply",{})
        e.call("finish",{"status":"paid"})
        self.assertFalse(e.score()["success"])
