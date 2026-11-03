import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tooluse_pilot.research import generate
from tooluse_pilot.executable_runner import run_candidate

class _Output:
    def __init__(self, value):self.value=value
    def model_dump(self, exclude_none=True):return self.value

class MockResponses:
    def __init__(self):self.step=0
    def create(self, **kwargs):
        self.step+=1
        assert kwargs["model"]=="fake"
        if self.step==1:
            items=[{"type":"function_call","call_id":"c1","name":"read_order","arguments":"{}"}]
        elif self.step==2:
            items=[{"type":"function_call","call_id":"c2","name":"read_order","arguments":"{}"}]
        elif self.step==3:
            history=kwargs["input"]
            obj=json.loads(history[-1]["output"])["result"]["order"]
            items=[{"type":"function_call","call_id":"c3","name":"settle_order","arguments":json.dumps(obj)}]
        else:items=[]
        output=[_Output(x) for x in items]
        return N(id=f"resp-{self.step}",output=output,usage=N(model_dump=lambda exclude_none=True:{"input_tokens":4,"output_tokens":5,"total_tokens":9}))
def as_calls(resp):
    return [N(id=x.value["call_id"],function=N(name=x.value["name"],arguments=x.value["arguments"])) for x in resp.output]
class ExecutableRunnerTests(unittest.TestCase):
    def test_runner_and_usage(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td)
            cand=base/"candidate.json"
            cand.write_text(json.dumps(generate("state_change",3)))
            cfg=base/"models.json"
            cfg.write_text(json.dumps({"models":{"fake":{"model":"fake","api_type":"responses","retry_limit":0}}}))
            mock=MockResponses()
            # Mock outputs are simple objects and compatible with gateway extraction.
            original=None
            import tooluse_pilot.executable_runner as module
            original=module.get_responses_calls
            module.get_responses_calls=as_calls
            try:
                result=run_candidate(cand,cfg,"fake",base/"usage.sqlite",client_factory=lambda:N(responses=mock))
            finally:module.get_responses_calls=original
            self.assertEqual(result["requests"],4)
            self.assertTrue(result["score"]["success"])
            self.assertEqual(result["tool_calls"],3)
            from tooluse_pilot.ledger import summary
            self.assertEqual(summary(base/"usage.sqlite")[0]["requests"],4)

if __name__=="__main__":unittest.main()
