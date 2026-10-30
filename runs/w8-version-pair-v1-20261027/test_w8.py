import sys,unittest,tempfile,json,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from w8_data import create
from independent_w7 import oracle
from tooluse_pilot.w8_task import Environment
class Tests(unittest.TestCase):
 def make(self,condition):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);p=Path(t.name)/'c';case,d=create(p,condition);return Environment(case,p),d,p
 def test_static_status_and_no_change(self):
  e,d,p=self.make('static');self.assertEqual(e.call('get_status',{})['current_revision'],'R1');r=e.call('read_rows',{'source':'grades'});self.assertEqual(r['read_revision'],r['current_revision'])
 def test_change_detectable_and_once(self):
  e,d,p=self.make('dynamic');first=e.call('read_rows',{'source':'grades'});self.assertEqual(first['read_revision'],'R1');self.assertEqual(first['current_revision'],'R2');self.assertTrue(first['stale'])
  second=e.call('read_rows',{'source':'grades'});self.assertEqual(second['read_revision'],'R2');self.assertEqual(second['current_revision'],'R2');self.assertEqual(len(first['rows']),len(second['rows']))
  self.assertEqual(e.call('get_status',{})['changed_record_ids'],['g-B2-s05-r2'])
 def test_stale_write_no_side_effect_and_recovery(self):
  e,d,p=self.make('dynamic');r=e.call('write_submission',{'expected_revision':'R1','rows_json':json.dumps(oracle(d))});self.assertFalse(r['accepted']);self.assertFalse((p/'submission.xlsx').exists());self.assertFalse(e.finished)
  e.call('read_rows',{'source':'grades'});e.call('write_submission',{'expected_revision':'R2','rows_json':json.dumps(oracle(e.data))});e.call('finish',{});self.assertTrue(e.score()['success'])
 def test_wrong_saved_answer_can_be_repaired_before_finish(self):
  e,d,p=self.make('static');rows=oracle(d);rows[0][2]=0;e.call('write_submission',{'expected_revision':'R1','rows_json':json.dumps(rows)});self.assertFalse(e.score()['answer_success']);e.call('write_submission',{'expected_revision':'R1','rows_json':json.dumps(oracle(d))});e.call('finish',{});self.assertTrue(e.score()['success'])
 def test_wrong_finish_does_not_leak_answer(self):
  e,d,p=self.make('static');rows=oracle(d);rows[0][2]=0;e.call('write_submission',{'expected_revision':'R1','rows_json':json.dumps(rows)});r=e.call('finish',{});self.assertTrue(r['finished']);self.assertNotIn('expected',r);self.assertFalse(e.score()['answer_success']);self.assertTrue(e.score()['task_completed'])
if __name__=='__main__':unittest.main()
