import json,tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import generate
from tooluse_pilot.w6_run_audit import audit

class W6RunAuditTests(unittest.TestCase):
    def test_historical_failure_without_gate_success(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"case";generate(2,root)
            run={"state":"max_requests","score":{"success":False,"checks":{"initial_delivered":False}},
                 "events":[{"event":"tool_call","tool":"receive_update","result":{"ok":False,"error":"first-stage deliverables incorrect or unsaved"}},
                           {"event":"tool_call","tool":"save_workbook","result":{"ok":True}},
                           {"event":"tool_call","tool":"receive_update","result":{"ok":False,"error":"first-stage deliverables incorrect or unsaved"}}]}
            (root/"run_result.json").write_text(json.dumps(run),encoding="utf-8")
            result=audit(root)
            self.assertEqual(result["gate_rejections"],2)
            self.assertFalse(result["recovered_after_gate_failure"])
            self.assertTrue(result["first_gate_before_successful_save"])
            self.assertEqual(result["model_requests_executed"],0)
    def test_recovery_must_follow_failed_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/"case";generate(0,root)
            run={"state":"finished","score":{"success":True},
                 "events":[{"event":"tool_call","tool":"receive_update","result":{"ok":False,"error":"stage_one_failed: summary_mismatch"}},
                           {"event":"tool_call","tool":"save_workbook","result":{"ok":True}},
                           {"event":"tool_call","tool":"receive_update","result":{"ok":True,"result":{}}}]}
            (root/"run_result.json").write_text(json.dumps(run),encoding="utf-8")
            self.assertTrue(audit(root)["recovered_after_gate_failure"])
