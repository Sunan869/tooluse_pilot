import shutil,tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import generate,reference,Environment,oracle,report

class W6ReconciliationTests(unittest.TestCase):
    def test_all_three_scenarios_have_distinct_final_answers(self):
        winners=[]
        for seed in range(3):
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp)/"case";case=generate(seed,root)
                before=(root/"reconciliation.xlsx").read_bytes()
                copy=Path(temp)/"copy";shutil.copytree(root,copy)
                result=reference(case,copy)
                self.assertTrue(result["success"],result)
                winners.append(result["expected"][2])
                self.assertEqual(before,(root/"reconciliation.xlsx").read_bytes())
        self.assertEqual(winners,["Beta","Gamma","Delta"])
    def test_stale_deliverables_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"case";case=generate(0,root)
            env=Environment(case,root)
            ans=oracle(env.wb)
            for cell,value in zip(("B2","B3","B4","B5"),ans):
                env.call("write_summary",{"cell":cell,"value":value})
            env.call("save_workbook",{})
            env.call("write_report",{"text":report(ans)})
            env.call("receive_update",{})
            env.call("finish",{})
            score=env.score()
            self.assertFalse(score["success"])
            self.assertFalse(score["checks"]["result"])
            self.assertFalse(score["checks"]["revised_saved"])
            env.close()
    def test_no_early_update(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"case";case=generate(2,root)
            env=Environment(case,root)
            with self.assertRaises(ValueError):env.call("receive_update",{})
            env.close()
