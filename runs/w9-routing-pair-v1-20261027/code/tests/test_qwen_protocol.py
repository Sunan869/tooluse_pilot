"""Offline fake-vLLM tests. No network or paid API usage."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch
from tooluse_pilot.real_file_dynamic import generate
from tooluse_pilot.executable_runner import run_candidate

class FakeMessage:
    def __init__(self, calls):
        self.tool_calls=calls
    def model_dump(self, exclude_none=True):
        return {"role":"assistant","tool_calls":[
            {"id":c.id,"type":"function","function":{"name":c.function.name,
              "arguments":c.function.arguments}} for c in self.tool_calls]}

class FakeLocal:
    def __init__(self):
        self.requests=[]
        self.chat=NS(completions=NS(create=self.create))
    def create(self, **kwargs):
        self.requests.append(kwargs)
        # No tool calls: test transport/shape and safe artifact preservation.
        return NS(id="mock-"+str(len(self.requests)),
                  usage=None,choices=[NS(message=FakeMessage([]))])

class QwenProtocolTests(unittest.TestCase):
    def test_chat_completions_local_config_and_artifacts(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);case=generate(3,p/"case")
            config=p/"local.json"
            config.write_text(json.dumps({"models":{"qwen":{
                "model":"Qwen3.8-27B","provider":"local_vllm",
                "api_type":"chat_completions",
                "request_options":{"extra_body":{"chat_template_kwargs":{
                    "enable_thinking":False}}}}}}),encoding="utf-8")
            fake=FakeLocal()
            with patch("tooluse_pilot.executable_runner.record"):
                out=run_candidate(p/"case"/"candidate.json",config,"qwen",
                                  db_path=str(p/"usage.sqlite"),
                                  max_requests=1,client_factory=lambda:fake)
            self.assertEqual(out["state"],"finished")
            self.assertFalse(out["score"]["success"])
            self.assertEqual(len(fake.requests),1)
            self.assertEqual(fake.requests[0]["model"],"Qwen3.8-27B")
            self.assertEqual(fake.requests[0]["extra_body"]["chat_template_kwargs"]["enable_thinking"],False)
            self.assertEqual(fake.requests[0]["tools"][0]["type"],"function")
            self.assertEqual(fake.requests[0]["messages"][0]["role"],"system")
            self.assertTrue((Path(out["artifact_dir"])/"run_result.json").exists())
            saved=json.loads((Path(out["artifact_dir"])/"run_result.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["run_id"],out["run_id"])
