"""No-API checks for sandbox encoding probe and binary subprocess capture."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_host_io_probe import sandbox_io_preflight, assert_repo_sandbox, REPO_ROOT
from tooluse_pilot.sandbox import DockerTools


class SandboxEncodingTests(unittest.TestCase):
    def test_loaded_sandbox_is_this_repository(self):
        path=Path(assert_repo_sandbox())
        self.assertEqual(path,(REPO_ROOT/"tooluse_pilot"/"sandbox.py").resolve())

    def test_import_guard_rejects_old_editable_checkout(self):
        import spreadsheetbench2_host_io_probe as probe
        with patch.object(probe.sandbox_module,"__file__",r"E:\\old_project\\tooluse_pilot\\sandbox.py"):
            with self.assertRaisesRegex(RuntimeError,"WRONG_SANDBOX_IMPORT"):
                assert_repo_sandbox()

    def test_dockertools_uses_binary_pipes_and_replaces_malformed_bytes(self):
        obj=DockerTools.__new__(DockerTools)
        obj.image="sandbox-image"
        obj.root=Path("/tmp/fake-workspace")
        obj.timeout=10
        obj.calls=[]
        data=SimpleNamespace(returncode=0,
                             stdout=("中文✓"*10000).encode("utf-8")+bytes([148]),
                             stderr=b"bad-utf8-"+bytes([148]))
        with patch("tooluse_pilot.sandbox.subprocess.run",return_value=data) as run:
            result=obj._exec("execute_python","print('check')")
        self.assertEqual(result["exit_code"],0)
        self.assertIn("中文",result["stdout"])
        self.assertIn("\ufffd",result["stdout"])
        self.assertIn("\ufffd",result["stderr"])
        self.assertIs(run.call_args.kwargs["text"],False)

    def test_probe_classifies_invalid_stdout_without_api(self):
        class FakeAgent:
            def __init__(self,*args,**kwargs):
                self.closed=False
            def execute_python(self,code):
                return {"exit_code":0,"stdout":"中文✓\ufffd","stderr":""}
            def execute_shell(self,code):
                return {"exit_code":0,"stdout":"中文✓\ufffd","stderr":""}
            def close(self):
                self.closed=True
        with patch("spreadsheetbench2_host_io_probe.DockerTools",FakeAgent):
            result=sandbox_io_preflight()
        self.assertTrue(result["pass"])

    def test_failed_probe_rejects_nonzero_exit(self):
        class FakeAgent:
            def __init__(self,*args,**kwargs):pass
            def execute_python(self,code):
                return {"exit_code":1,"stdout":"","stderr":"failed"}
            def execute_shell(self,code):
                return {"exit_code":0,"stdout":"中文\ufffd","stderr":""}
            def close(self):pass
        with patch("spreadsheetbench2_host_io_probe.DockerTools",FakeAgent):
            result=sandbox_io_preflight()
        self.assertFalse(result["pass"])


if __name__=="__main__":
    unittest.main()
