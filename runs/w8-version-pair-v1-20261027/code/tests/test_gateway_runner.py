import json, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from tooluse_pilot.generate import make_case
from tooluse_pilot.gateway import run_gateway
from tooluse_pilot.ledger import summary, usage_fields

class FakeMessage:
    tool_calls=[]
    def model_dump(self,exclude_none=True):return {'role':'assistant','content':'Done'}

class FakeUsage:
    def model_dump(self,exclude_none=True):
        return {'prompt_tokens':100,'completion_tokens':20,'total_tokens':120,'prompt_tokens_details':{'cached_tokens':15},'completion_tokens_details':{'reasoning_tokens':2}}

class FakeCompletion:
    id='mock-req-1'
    choices=[SimpleNamespace(message=FakeMessage())]
    usage=FakeUsage()

class FakeClient:
    def __init__(self):self.chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kw:FakeCompletion()))

class GatewayRunnerTests(unittest.TestCase):
    def test_request_usage_and_no_stale_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=make_case(Path(tmp)/'case',seed=3,count=30)
            out=root/'output';out.mkdir();(out/'anomalies.csv').write_text('fake')
            cfg=Path(tmp)/'config.json'
            cfg.write_text(json.dumps({'models':{'mock':{'model':'test-model','provider':'mock'}}}))
            db=Path(tmp)/'usage.sqlite'
            result=run_gateway(root,cfg,'mock',db_path=db,client_factory=FakeClient)
            self.assertEqual(result['requests'],1)
            self.assertEqual(result['score']['result_score'],0)
            rows=summary(db)
            self.assertEqual(rows[0]['input_tokens'],100)
            self.assertEqual(rows[0]['cached_tokens'],15)
            self.assertEqual(rows[0]['unknown_cost_requests'],1)
    def test_responses_usage_normalization(self):
        u=usage_fields({'input_tokens':50,'output_tokens':21,'total_tokens':71,'input_tokens_details':{'cached_tokens':20},'output_tokens_details':{'reasoning_tokens':5}})
        self.assertEqual(u['cached_tokens'],20)
        self.assertEqual(u['reasoning_tokens'],5)
if __name__=='__main__':unittest.main()
