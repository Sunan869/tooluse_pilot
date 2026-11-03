import json,tempfile,unittest,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from tooluse_pilot.executable_runner import run_candidate
from tooluse_pilot.research import generate

class BudgetTests(unittest.TestCase):
    def test_full_file_runner_with_scripted_reference_tools(self):
        batch=Path(__file__).resolve().parents[2]
        for variant in [0,1]:
            calls=json.loads((batch/'references'/f'case-{variant}'/'reference-result.json').read_text())['reference_calls']
            class Output:
                def __init__(self,value):self.value=value;self.__dict__.update(value)
                def model_dump(self,exclude_none=True):return self.value
            steps=iter([calls[i:i+4] for i in range(0,len(calls),4)])
            def create(**kwargs):
                group=next(steps,[])
                output=[Output({'type':'function_call','call_id':f'c{i}','name':x['tool'],'arguments':json.dumps(x['args'])}) for i,x in enumerate(group)]
                return SimpleNamespace(id='offline',output=output,usage=None)
            with tempfile.TemporaryDirectory() as temp:
                root=Path(temp);cfg=root/'config.json';cfg.write_text(json.dumps({'models':{'fake':{'model':'fake','api_type':'responses'}}}))
                previous=Path.cwd()
                try:
                    os.chdir(root)
                    result=run_candidate(batch/'candidates'/f'case-{variant}'/'candidate.json',cfg,'fake',root/'usage.sqlite',25,80,client_factory=lambda:SimpleNamespace(responses=SimpleNamespace(create=create)))
                finally:os.chdir(previous)
                self.assertTrue(result['score']['success'],result['score'])
                self.assertEqual(result['requests'],8)
                self.assertEqual(result['state'],'finished')
                self.assertEqual(result['tool_calls'],28)

    def test_retries_are_included_in_actual_request_budget(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);candidate=root/'candidate.json';config=root/'config.json'
            candidate.write_text(json.dumps(generate('state_change',3)))
            config.write_text(json.dumps({'models':{'fake':{'model':'fake','api_type':'responses','retry_limit':3}}}))
            calls=[]
            def fail(**kwargs):
                calls.append(kwargs);raise TimeoutError('offline simulated timeout')
            client=SimpleNamespace(responses=SimpleNamespace(create=fail))
            with patch('tooluse_pilot.executable_runner._is_retryable',return_value=True),patch('tooluse_pilot.executable_runner.time.sleep'):
                result=run_candidate(candidate,config,'fake',root/'usage.sqlite',2,80,client_factory=lambda:client)
            self.assertEqual(len(calls),2)
            self.assertEqual(result['requests'],2)
            self.assertEqual(result['state'],'api_error')
