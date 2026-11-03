import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tooluse_pilot.real_file_task import generate,reference
from tooluse_pilot.executable_runner import run_candidate

class IsolatedFileCaseTests(unittest.TestCase):
    def test_reference_copy_does_not_change_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"input";case=generate(2,root)
            before=(root/"procurement.xlsx").read_bytes()
            output=Path(tmp)/"reference"
            import shutil
            shutil.copytree(root,output)
            self.assertTrue(reference(case,output)["success"])
            self.assertEqual(before,(root/"procurement.xlsx").read_bytes())

    def test_runner_has_distinct_workspace_even_when_request_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"input";generate(2,root)
            before=(root/"procurement.xlsx").read_bytes()
            config=Path(tmp)/"models.json"
            config.write_text(json.dumps({"models":{"stub":{"model":"dummy","api_type":"responses"}}}),encoding="utf-8")
            class Failing:
                class responses:
                    @staticmethod
                    def create(**kwargs):
                        raise RuntimeError("network unavailable")
            with patch("tooluse_pilot.executable_runner.record"):
                output=run_candidate(root/"candidate.json",config,"stub",
                                     db_path=str(Path(tmp)/"usage.sqlite"),
                                     client_factory=lambda:Failing(),max_requests=1)
            self.assertEqual(output["state"],"api_error")
            self.assertNotEqual(Path(output["artifact_dir"]).resolve(),root.resolve())
            self.assertEqual(before,(root/"procurement.xlsx").read_bytes())
