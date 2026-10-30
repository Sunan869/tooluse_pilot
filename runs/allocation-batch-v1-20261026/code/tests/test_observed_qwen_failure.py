"""Regression of a real local-Qwen failure: stale supplier and false coverage claims."""
import shutil
import tempfile
import unittest
from pathlib import Path
from openpyxl import load_workbook
from tooluse_pilot.real_file_dynamic import generate,Environment,expected,final_report_matches

class ObservedFailureRegression(unittest.TestCase):
    def test_qwen_wrong_final_workbook_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            folder=Path(temp)/"case"
            case=generate(0,folder)
            env=Environment(case,folder)
            first=expected(env.workbook,160000,["Beijing"])
            for cell,value in zip(("B4","B5","B6"),first):
                env.call("write_cell",{"sheet":"Decision","cell":cell,"value":value})
            env.call("save_workbook",{})
            env.call("write_report",{"text":f"Recommended {first[0]} for {first[1]:s} CNY; {first[2]} eligible."})
            env.call("receive_update",{})
            # Mimic observed behavior: keep Alpha, change only eligible count,
            # write a plausible but false report, and finalize.
            env.call("write_cell",{"sheet":"Decision","cell":"B6","value":"3"})
            env.call("write_report",{"text":(
                "Recommended supplier: Alpha\nPrice: 100729\n"
                "Eligible suppliers: 3\n"
                "Alpha: Beijing yes, Shenzhen yes\n"
                "Beta: Beijing yes, Shenzhen yes"
            )})
            env.call("save_workbook",{})
            env.call("finish",{})
            score=env.score()
            self.assertFalse(score["success"])
            self.assertFalse(score["checks"]["result"])
            self.assertFalse(score["checks"]["report"])
            env.close()

    def test_correct_reference_report_is_accepted(self):
        self.assertTrue(final_report_matches(
            "Recommended Beta for 116788 CNY; 1 eligible.",
            "Beta","116788",1,["Alpha","Beta","Gamma","Delta"]
        ))

    def test_conflicting_recommendations_rejected(self):
        self.assertFalse(final_report_matches(
            "Recommended supplier: Beta\nChosen: Alpha\nEligible count: 1\n116788 CNY",
            "Beta","116788",1,["Alpha","Beta","Gamma","Delta"]
        ))
