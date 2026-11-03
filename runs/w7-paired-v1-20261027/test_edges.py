import unittest,json
from test_w7 import W7Tests
from independent_w7 import oracle
class EdgeTests(W7Tests):
 def test_filtered_coverage_and_point_access(self):
  e,d=self.make('coverage')
  for s in ('enrollment','grades'):
   for row in d[s]:
    if row['batch_id']=='B2':self.assertTrue(e.call('get_record',{'source':s,'record_id':row['record_id']})['found'])
  e.call('write_submission',{'rows_json':json.dumps(oracle(d))});e.call('finish',{})
  self.assertTrue(e.score()['coverage_complete']);self.assertTrue(e.score()['evidence_valid'])
 def test_cursor_rejected_and_recoverable(self):
  e,d=self.make('coverage');r=e.call('read_rows',{'source':'grades'})
  with self.assertRaises(ValueError):e.call('read_rows',{'source':'enrollment','cursor':r['next_cursor']})
  e.invalid_actions+=1
  e.call('write_submission',{'rows_json':json.dumps(oracle(d))});e.call('finish',{})
  self.assertTrue(e.score()['success']);self.assertFalse(e.score()['strict_process_success'])
 def test_wrong_batch_and_wrong_tie_and_inactive(self):
  for change in ('batch','tie','inactive','score'):
   e,d=self.make('clean');rows=oracle(d)
   if change=='batch':rows[0][3]='B1'
   if change=='tie':rows[2][0]='s08'
   if change=='inactive':rows[0][0]='s04';rows[0][2]=99
   if change=='score':rows[0][2]=194
   e.call('write_submission',{'rows_json':json.dumps(rows)});e.call('finish',{});self.assertFalse(e.score()['answer_success'])
 def test_references_diagnostic(self):
  e,d=self.make('clean');rows=oracle(d);rows[0][4]='missing'
  e.call('write_submission',{'rows_json':json.dumps(rows)});e.call('finish',{})
  self.assertTrue(e.score()['answer_success']);self.assertFalse(e.score()['evidence_valid'])
 def test_empty_filter_is_explicit(self):
  e,d=self.make('coverage');r=e.call('read_rows',{'source':'grades','batch_id':'B9'})
  self.assertEqual(r['rows'],[]);self.assertEqual(r['total_matching'],0);self.assertFalse(r['has_more'])
if __name__=='__main__':unittest.main()
