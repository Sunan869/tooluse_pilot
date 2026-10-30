import tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_multisheet import generate,Environment,reference
class MultiSheetTests(unittest.TestCase):
    def test_reference(self):
        for seed in range(8):
            with tempfile.TemporaryDirectory() as td:
                root=Path(td)/"case"
                case=generate(seed,root)
                self.assertTrue(reference(case,root)["success"])
    def test_naive_duplicate_sum_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case";case=generate(0,root)
            env=Environment(case,root)
            env.call("write_summary",{"cell":"B2","value":"999999"})
            env.call("write_summary",{"cell":"B3","value":"4"})
            env.call("write_summary",{"cell":"B4","value":"A-003"})
            env.call("save_workbook",{})
            env.call("write_report",{"text":"999999 4 A-003"})
            env.call("finish",{})
            self.assertFalse(env.score()["success"])
            env.close()
