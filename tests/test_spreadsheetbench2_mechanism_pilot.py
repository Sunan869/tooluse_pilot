"""Offline pilot-plan tests: no API calls, credentials or Docker needed."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_mechanism_pilot import (
    aggregate, make_plan, run_plan, report, infrastructure_error, model_preflight)

DATA=Path(os.getenv("SSB2_NEW_DATASET","runs/ssb2-discovered-v2"))


class PilotSafeguards(unittest.TestCase):
    def test_execute_opt_in_is_mandatory(self):
        with self.assertRaisesRegex(ValueError,"--execute"):
            run_plan(Path("nothing.json"),Path("not_created"),
                     api_type="chat_completions",max_requests=25,max_tools=60,
                     sandbox_image="unused",max_cases=1,execute=False)

    def test_summary_does_not_equate_no_artifact_with_wrong_formula(self):
        report_data=aggregate([
            {"case_id":"a","state":"max_requests","artifact_created":False,"pass":False},
            {"case_id":"b","state":"finished","artifact_created":True,"pass":True},
            {"case_id":"c","state":"finished","artifact_created":True,"pass":False}])
        self.assertEqual((report_data["cases"],report_data["delivered_xlsx"],
                          report_data["strict_passes"]),(3,2,1))

    def test_502_is_infrastructure_not_model_failure(self):
        self.assertEqual(infrastructure_error(Exception("Error code: 502")),"upstream_http_502")
        self.assertEqual(infrastructure_error(Exception("Error code: 503")),"upstream_http_503")
        self.assertIsNone(infrastructure_error(ValueError("Business formula wrong")))
        result=aggregate([{"case_id":"A","state":"runner_error",
                           "infrastructure_error":"upstream_http_502",
                           "pass":None,"artifact_created":False}])
        self.assertEqual(result["valid_model_evaluations"],0)
        self.assertEqual(result["infrastructure_errors"],1)

    def test_preflight_chat_tool_call(self):
        from types import SimpleNamespace as NS
        call=NS(function=NS(name="execute_python"))
        response=NS(choices=[NS(message=NS(tool_calls=[call]))])
        client=NS(chat=NS(completions=NS(create=lambda **kw: response)))
        result=model_preflight(client,"Qwen3.8-Flash-Next-AWQ-INT4","chat_completions")
        self.assertTrue(result["tool_calls_supported"])

    def test_no_secret_in_pilot_reporting(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            (root/"summary.json").write_text(
                json.dumps([{"case_id":"X","state":"max_requests","pass":False,
                             "artifact_created":False}]),encoding="utf-8")
            self.assertEqual(report(root)["cases"],1)


@unittest.skipUnless((DATA/"private"/"oracle.json").is_file(),
                     "Requires generated 136-case dataset")
class PilotPlanIntegration(unittest.TestCase):
    def test_balanced_reproducible_plan_and_secret_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/"a.json"
            b=Path(td)/"b.json"
            result=make_plan(DATA,a,6,2)
            make_plan(DATA,b,6,2)
            first=json.loads(a.read_text(encoding="utf-8"))
            second=json.loads(b.read_text(encoding="utf-8"))
            self.assertEqual(first["cases"],second["cases"])
            self.assertEqual(result["selected"],8)
            self.assertEqual(result["singles"],6)
            self.assertEqual(result["compounds"],2)
            self.assertEqual(len({c["id"] for c in first["cases"]}),8)
            self.assertEqual(sum(c["fault_count"]>1 for c in first["cases"]),2)
            self.assertEqual(first["run_confirmation_required"],True)
            for case in first["cases"]:
                self.assertNotIn("correct",case)
                self.assertNotIn("mutated",case)
                self.assertNotIn("faults",case)
            with self.assertRaises(FileExistsError):
                make_plan(DATA,a,6,2)


if __name__=="__main__":
    unittest.main()
