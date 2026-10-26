import tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import generate,Environment,oracle,report_valid,reference
from tooluse_pilot.failure_attribution import diagnose

class RecoveryFeedbackTests(unittest.TestCase):
    def test_report_variants_and_conflicts(self):
        correct=("23000","4","Alpha","8000")
        for sample in ("total=23000 count=4 winner=Alpha amount=8000",
                       "Total: 23000\\nCount: 4\\nWinner: Alpha\\nAmount: 8000",
                       "total 23000, count 4, winner Alpha, amount 8000"):
            self.assertTrue(report_valid(sample.replace("\\n","\n"),correct),sample)
        self.assertFalse(report_valid("total=23000 count=4 winner=Alpha amount=8000; winner=Delta",correct))
        self.assertFalse(report_valid("total=23000 count=3 winner=Alpha amount=8000",correct))

    def test_gate_reports_missing_save_and_wrong_values(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case";case=generate(2,root);env=Environment(case,root)
            with self.assertRaisesRegex(ValueError,"workbook_not_saved"):
                env.call("receive_update",{})
            for cell,value in zip(("B2","B3","B4","B5"),("12200","4","Delta","5200")):
                env.call("write_summary",{"cell":cell,"value":value})
            env.call("save_workbook",{})
            env.call("write_report",{"text":"total=12200 count=4 winner=Delta amount=5200"})
            with self.assertRaisesRegex(ValueError,"summary_mismatch"):
                env.call("receive_update",{})
            answer=oracle(env.wb)
            for cell,value in zip(("B2","B3","B4","B5"),answer):
                env.call("write_summary",{"cell":cell,"value":value})
            env.call("save_workbook",{})
            env.call("write_report",{"text":"total="+answer[0]+" count="+answer[1]+" winner="+answer[2]+" amount="+answer[3]})
            self.assertEqual(env.call("receive_update",{})["max_per_order"],8000)
            env.close()

    def test_reference_all_seeds_and_recovery_attribution(self):
        for seed in range(3):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)/"case";case=generate(seed,root)
                self.assertTrue(reference(case,root)["success"])
        events=[{"event":"tool_call","tool":"receive_update","result":{"ok":False,"error":"stage_one_failed: summary_mismatch"}},
                {"event":"tool_call","tool":"receive_update","result":{"ok":True,"result":{"max_per_order":8000}}}]
        out=diagnose({"score":{"success":True},"events":events})
        self.assertTrue(next(x for x in out["categories"] if x["category"]=="revision_gate_recovery")["evidence"]["recovered"])
