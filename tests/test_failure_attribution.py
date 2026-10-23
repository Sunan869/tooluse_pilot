import unittest
from tooluse_pilot.failure_attribution import diagnose,batch

class AttributionTests(unittest.TestCase):
    def test_observed_qwen_errors(self):
        run={"run_id":"sample","candidate_id":"file-dynamic-0","state":"finished",
             "model":"Qwen3.8-27B","tool_calls":3,"invalid_tool_actions":2,
             "score":{"success":False,"checks":{"initial_delivered":True,
                "update_received":True,"requirements":True,"result":False,
                "report":False,"finished":True}},
             "events":[{"event":"tool_call","tool":"inspect_sheet",
                        "arguments":'{"sheet":"Sheet1"}',
                        "result":{"ok":False,"error":"unknown sheet"}},
                       {"event":"tool_call","tool":"write_cell",
                        "arguments":'{"cell":"130000"}',
                        "result":{"ok":False,"error":"only output Decision cells may be modified"}}]}
        out=diagnose(run)
        self.assertFalse(out["passed"])
        self.assertEqual(out["invalid_tool_actions"],2)
        self.assertIn("sheet_discovery_errors",out["category_names"])
        self.assertIn("cell_argument_errors",out["category_names"])
        self.assertIn("failed_result",out["category_names"])
        self.assertIn("failed_report",out["category_names"])

    def test_success_not_labelled_as_failure(self):
        out=diagnose({"score":{"success":True,"checks":{"result":True,"report":True}},
                      "state":"finished","events":[]})
        self.assertTrue(out["passed"])
        self.assertEqual(out["category_names"],[])

    def test_origin_priority(self):
        base={"score":{"success":False,"checks":{"result":False}},"state":"finished"}
        self.assertEqual(diagnose(base)["origin"],"model_behavior")
        flagged={**base,"evaluation_issue":True}
        self.assertEqual(diagnose(flagged)["origin"],"environment_or_oracle")
        interrupted={**flagged,"state":"api_error"}
        self.assertEqual(diagnose(interrupted)["origin"],"transport")

    def test_transport_not_model_execution_failure(self):
        out=diagnose({"score":{"success":False},"state":"api_error"})
        self.assertEqual(out["category_names"],["transport_failure"])
        self.assertEqual(out["origin"],"transport")
