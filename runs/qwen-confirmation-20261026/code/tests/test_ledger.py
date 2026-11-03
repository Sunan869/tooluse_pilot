import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.ledger import record,summary,export_csv,calculate_cost,usage_fields
from tooluse_pilot.gateway import _safe_tool

class LedgerTests(unittest.TestCase):
    def test_cost(self):
        self.assertEqual(calculate_cost({'prompt_tokens':1000000,'completion_tokens':200000,'cached_tokens':400000}, {'input_per_million':'2','cached_input_per_million':'0.5','output_per_million':'8'}),'3.00000000')
        self.assertIsNone(calculate_cost({'prompt_tokens':100,'completion_tokens':20,'cached_tokens':None},{'input_per_million':'2','cached_input_per_million':'0.5','output_per_million':'8'}))
    def test_usage(self):
        u=usage_fields({'prompt_tokens':120,'completion_tokens':35,'total_tokens':155,'prompt_tokens_details':{'cached_tokens':25},'completion_tokens_details':{'reasoning_tokens':10}})
        self.assertEqual((u['cached_tokens'],u['reasoning_tokens']),(25,10))
    def test_ledger(self):
        with tempfile.TemporaryDirectory() as d:
            db=Path(d)/'ledger.sqlite'
            record(db,run_id='r',task_id='t',mode='structured',provider='x',model='m',attempt=1,status='ok',prompt_tokens=10,completion_tokens=12,total_tokens=22,cached_tokens=0,reasoning_tokens=0,tool_calls=1,estimated_cost='0.002',currency='CNY')
            self.assertEqual(summary(db)[0]['requests'],1)
            self.assertEqual(export_csv(db,Path(d)/'usage.csv'),1)
    def test_reject_unknown_tool(self):
        with self.assertRaises(ValueError): _safe_tool(None,'delete_files',{})
if __name__=='__main__':unittest.main()
