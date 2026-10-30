import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.research_calibration import plan,analyze,read_results

class CalibrationTests(unittest.TestCase):
    def test_plan_does_not_mutate_candidates(self):
        with tempfile.TemporaryDirectory() as td:
            d=Path(td)
            for i in range(4):
                sub=d/str(i);sub.mkdir()
                (sub/"candidate.json").write_text(json.dumps({"id":f"demo-{i}","family":"demo","task":"x"}))
            result=plan([d],2)
            self.assertEqual(result["candidate_count"],2)
            self.assertEqual(result["paid_requests"],0)
            self.assertEqual(len(list(d.rglob("candidate.json"))),4)

    def test_transport_errors_are_not_model_failures(self):
        reports=[
            {"candidate_id":"a","family":"demo","model":"one","state":"finished",
             "score":{"success":True},"requests":2,"tool_calls":1,"estimated_cost":None},
            {"candidate_id":"b","family":"demo","model":"one","state":"api_error",
             "score":{"success":False},"requests":3,"tool_calls":0,"estimated_cost":None},
            {"candidate_id":"c","family":"demo","model":"one","state":"finished",
             "score":{"success":False},"requests":4,"tool_calls":3,"estimated_cost":1.5},
        ]
        result=analyze(reports)["family_metrics"]["demo"]
        self.assertEqual(result["observed_pass_rate"],0.5)
        self.assertEqual(result["api_errors"],1)
        self.assertEqual(result["unpriced_runs"],2)
        self.assertEqual(result["known_cost"],1.5)

    def test_duplicate_results_rejected(self):
        result={"candidate_id":"same","family":"demo","model":"a","state":"finished","score":{}}
        with self.assertRaises(ValueError):analyze([result,result])
