import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tooluse_pilot.sandbox import DockerTools

class DockerOutputDecodingTests(unittest.TestCase):
    def test_utf8_and_invalid_bytes_do_not_use_system_codepage(self):
        tool=object.__new__(DockerTools)
        tool.root=Path("/tmp/example")
        tool.image="test-image"
        tool.timeout=5
        tool.calls=[]
        payload=SimpleNamespace(returncode=0,stdout="中文 ✓".encode("utf-8")+b"\xff",
                                stderr="错误".encode("utf-8"))
        with patch("tooluse_pilot.sandbox.subprocess.run",return_value=payload) as mocked:
            result=tool._exec("execute_python","print(1)")
        self.assertEqual(result["exit_code"],0)
        self.assertIn("中文 ✓",result["stdout"])
        self.assertIn("错误",result["stderr"])
        self.assertIn("\ufffd",result["stdout"])
        self.assertFalse(mocked.call_args.kwargs["text"])
        self.assertEqual(mocked.call_args.args[0][0],"docker")

if __name__=="__main__":unittest.main()
