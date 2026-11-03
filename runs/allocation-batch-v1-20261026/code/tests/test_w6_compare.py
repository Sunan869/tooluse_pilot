import json,tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import generate
from tooluse_pilot.w6_compare import compare,export

def put(root,seed,ok,passed):
    generate(seed,root)
    events=[{"event":"tool_call","tool":"receive_update","result":{"ok":False,"error":"stage_one_failed: summary_mismatch"}}]
    if ok:events.append({"event":"tool_call","tool":"receive_update","result":{"ok":True,"result":{}}})
    run={"state":"finished" if passed else "max_requests","score":{"success":passed},
         "events":events,"tool_calls":len(events),"invalid_tool_actions":int(not ok)}
    (root/"run_result.json").write_text(json.dumps(run),encoding="utf-8")

class PairedComparisonTests(unittest.TestCase):
    def test_old_failure_new_stage_progress(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old";new=Path(td)/"new"
            put(old,2,False,False);put(new,2,True,False)
            result=compare(old,new)
            self.assertEqual(result["outcome"],"improved_stage_progress")
            self.assertTrue(result["new"]["recovered_after_gate_failure"])
            out=Path(td)/"report"/"comparison.json"
            self.assertEqual(export(old,new,out)["model_requests_executed"],0)
            with self.assertRaises(FileExistsError):export(old,new,out)
    def test_mismatched_seed_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old";new=Path(td)/"new"
            put(old,1,False,False);put(new,2,True,True)
            with self.assertRaises(ValueError):compare(old,new)
    def test_success_is_not_automatically_attributed_to_feedback(self):
        with tempfile.TemporaryDirectory() as td:
            old=Path(td)/"old";new=Path(td)/"new"
            put(old,2,False,False);put(new,2,True,True)
            result=compare(old,new)
            self.assertEqual(result["outcome"],"improved_completion")
            self.assertTrue(result["limitations"])
