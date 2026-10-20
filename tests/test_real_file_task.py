import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.real_file_task import generate,Environment,reference
class FileTaskTests(unittest.TestCase):
    def test_reference_edits_actual_workbook(self):
        for seed in range(5):
            with tempfile.TemporaryDirectory() as td:
                p=Path(td)/"case"
                case=generate(seed,p)
                self.assertTrue(reference(case,p)["success"])
    def test_unsaved_changes_do_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"case";case=generate(0,p)
            e=Environment(case,p)
            e.call("write_cell",{"sheet":"Decision","cell":"B4","value":"Alpha"})
            e.call("finish",{})
            self.assertFalse(e.score()["success"])
            e.close()
    def test_fake_report_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"case";case=generate(1,p)
            e=Environment(case,p)
            e.call("write_report",{"text":"Recommended Alpha 125000"})
            e.call("finish",{})
            self.assertFalse(e.score()["success"])
            e.close()
