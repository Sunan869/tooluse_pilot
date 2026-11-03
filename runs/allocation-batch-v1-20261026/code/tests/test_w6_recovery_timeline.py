import unittest
from tooluse_pilot.failure_attribution import diagnose

def event(tool,ok=True,error=None):
    payload={"ok":ok}
    if error:payload["error"]=error
    return {"event":"tool_call","tool":tool,"result":payload}

class RecoveryTimelineTests(unittest.TestCase):
    def test_recovery_needs_success_after_error(self):
        events=[event("receive_update"),event("receive_update",False,"stage_one_failed: summary_mismatch"),event("save_workbook")]
        out=diagnose({"score":{"success":False},"events":events})
        detail=next(x["evidence"] for x in out["categories"] if x["category"]=="revision_gate_recovery")
        self.assertFalse(detail["recovered"])
        self.assertIsNone(detail["success_index"])
        self.assertEqual(detail["diagnostic_reasons"],["summary_mismatch"])
    def test_repair_actions_and_success_are_ordered(self):
        events=[event("receive_update",False,"stage_one_failed: workbook_not_saved, summary_mismatch"),
                event("read_sheet"),event("write_summary"),event("save_workbook"),event("write_report"),event("receive_update")]
        out=diagnose({"score":{"success":True},"events":events})
        detail=next(x["evidence"] for x in out["categories"] if x["category"]=="revision_gate_recovery")
        self.assertTrue(detail["recovered"])
        self.assertEqual(detail["success_index"],5)
        self.assertEqual(len(detail["correction_actions"]),4)
        self.assertEqual(detail["diagnostic_reasons"],["summary_mismatch","workbook_not_saved"])
    def test_old_generic_errors_do_not_create_fabricated_reasons(self):
        events=[event("receive_update",False,"first-stage deliverables incorrect or unsaved")]
        detail=next(x["evidence"] for x in diagnose({"score":{"success":False},"events":events})["categories"] if x["category"]=="revision_gate_recovery")
        self.assertEqual(detail["diagnostic_reasons"],[])
        self.assertFalse(detail["recovered"])
