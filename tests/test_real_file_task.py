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
    def test_save_without_correct_cells_does_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'case';case=generate(3,p)
            e=Environment(case,p)
            e.call('save_workbook',{})
            e.call('write_report',{'text':'Completed'})
            e.call('finish',{})
            self.assertFalse(e.score()['success'])
            self.assertFalse(e.score()['checks']['vendor'])
            e.close()

    def test_unsaved_correct_cells_are_not_accepted(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'case';case=generate(0,p)
            e=Environment(case,p)
            e.call('write_cell',{'sheet':'Decision','cell':'B4','value':'Delta'})
            e.call('write_cell',{'sheet':'Decision','cell':'B5','value':'138000'})
            e.call('write_cell',{'sheet':'Decision','cell':'B6','value':'3'})
            e.call('write_report',{'text':'Delta costs 138000'})
            e.call('finish',{})
            self.assertFalse(e.score()['success'])
            self.assertFalse(e.score()['checks']['workbook_changed_on_disk'])
            e.close()
    def test_fake_report_cannot_pass(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"case";case=generate(1,p)
            e=Environment(case,p)
            e.call("write_report",{"text":"Recommended Alpha 125000"})
            e.call("finish",{})
            self.assertFalse(e.score()["success"])
            e.close()
