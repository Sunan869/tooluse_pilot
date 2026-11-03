import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.real_file_dynamic import generate,reference
from tooluse_pilot.research_records import export_one,export_batch

class ResearchRecordTests(unittest.TestCase):
    def test_reference_record(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"candidate"
            c=generate(0,source)
            self.assertTrue(reference(c,source)["success"])
            result=export_one(source)
            self.assertTrue(result["artifact_consistent"])
            self.assertFalse(result["trace_available"])
            self.assertEqual(len(result["evidence_sha256"]["workbook"]),64)
    def test_export_rejects_overwrite_and_records_bad_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            candidate=root/"candidate"
            generate(2,candidate)
            out=root/"export"
            report=export_batch([candidate],out)
            self.assertEqual(report["failing_artifacts"],1)
            self.assertEqual(report["model_requests_executed"],0)
            with self.assertRaises(FileExistsError):
                export_batch([candidate],out)
