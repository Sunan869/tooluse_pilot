import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.real_file_dynamic import generate, reference
from tooluse_pilot.candidate_screening import select, export

class CandidateScreeningTests(unittest.TestCase):
    def test_no_trace_cannot_count_as_model_failure(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case"
            generate(0,root)
            result=select([root])
            self.assertEqual(result["by_decision"],{"insufficient_trace":1})
            self.assertFalse(result["candidates"][0]["candidate_evidence"])

    def test_reference_without_model_trace_stays_insufficient(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case"
            case=generate(0,root)
            self.assertTrue(reference(case,root)["success"])
            result=select([root])
            self.assertEqual(result["by_decision"],{"insufficient_trace":1})

    def test_trace_and_wrong_disk_artifacts_are_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case"
            generate(0,root)
            trace={"run_id":"synthetic","candidate_id":"file-dynamic-0","model":"fake",
                   "state":"finished","score":{"success":False,"checks":{"result":False}},
                   "events":[{"event":"tool_call","tool":"inspect_sheet",
                   "arguments":'{"sheet":"bad"}',"result":{"ok":False,"error":"unknown sheet"}}]}
            (root/"run_result.json").write_text(json.dumps(trace),encoding="utf-8")
            result=select([root])
            self.assertEqual(result["by_decision"],{"research_candidate":1})
            self.assertIn("sheet_discovery_errors",result["candidates"][0]["tool_error_categories"])
            path=Path(td)/"output.json"
            self.assertEqual(export([root],path)["model_requests_executed"],0)
            with self.assertRaises(FileExistsError):export([root],path)
