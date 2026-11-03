import json,tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import generate,reference,report
from tooluse_pilot.w6_rescore import export,rescore

class W6RescoreTests(unittest.TestCase):
    def make_reference_run(self,folder):
        case=generate(2,folder)
        score=reference(case,folder)
        expected=("23000","4","Alpha","8000")
        final=tuple(score["expected"])
        payload={"score":{**score,"success":False,"checks":{**score["checks"],"report":False}},
                 "invalid_tool_actions":0,
                 "events":[{"event":"tool_call","tool":"write_report","arguments":json.dumps({"text":report(expected)}),"result":{"ok":True}},
                           {"event":"tool_call","tool":"write_report","arguments":json.dumps({"text":report(final)+" Revised Policy and Corrections."}),"result":{"ok":True}}]}
        (folder/"run_result.json").write_text(json.dumps(payload),encoding="utf-8")
    def test_correct_artifacts_upgrade_report_only(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case";self.make_reference_run(root)
            original=(root/"run_result.json").read_bytes()
            result=rescore(root)
            self.assertEqual(result["changed_checks"]["report"],{"original":False,"revised":True})
            self.assertTrue(result["revised_score"]["success"])
            out=Path(td)/"revised.json"
            export(root,out)
            self.assertEqual(original,(root/"run_result.json").read_bytes())
            with self.assertRaises(FileExistsError):export(root,out)
    def test_wrong_report_remains_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case";self.make_reference_run(root)
            (root/"report.txt").write_text("Total: 999",encoding="utf-8")
            self.assertFalse(rescore(root)["revised_score"]["success"])
