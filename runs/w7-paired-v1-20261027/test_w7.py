import sys,json,tempfile,unittest,copy
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from w7_data import create,dataset
from independent_w7 import oracle
from tooluse_pilot.w7_task import Environment,answer_rows

class W7Tests(unittest.TestCase):
    def make(self,condition):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        case,data=create(Path(temp.name)/'case',condition);env=Environment(case,Path(temp.name)/'case');self.addCleanup(env.close)
        return env,data
    def test_gold_ids_tie_and_batch(self):
        d=dataset(20261027);self.assertEqual([r[:3:2] for r in oracle(d)],[['s03',95],['s01',92],['s06',91]])
        self.assertEqual(answer_rows(d),oracle(d))
    def test_clean_sources_complete(self):
        e,d=self.make('clean');r=e.call('read_rows',{'source':'grades'})
        self.assertEqual(len(r.get('rows',[])),18);self.assertFalse(r['has_more']);self.assertEqual(r['total_matching'],18)
    def test_coverage_complete_path_no_duplicates(self):
        e,d=self.make('coverage');rows=[];cursor=None
        while True:
            a={'source':'grades'}
            if cursor:a['cursor']=cursor
            r=e.call('read_rows',a);self.assertLessEqual(len(r.get('rows',[])),4);self.assertTrue('has_more' in r)
            rows+=r['rows']
            if not r['has_more']:break
            self.assertTrue(r['next_cursor']);cursor=r['next_cursor']
        self.assertEqual(len(rows),18);self.assertEqual(len({x['record_id'] for x in rows}),18)
    def test_only_cache_conflicts(self):
        e,d=self.make('conflict');r=e.call('read_rows',{'source':'cache'});self.assertEqual(len(r.get('rows',[])),8)
        byid={x['student_id']:x for x in r['rows']};self.assertEqual(byid['s02']['score'],99);self.assertEqual(byid['s06']['score'],89)
        self.assertEqual(e.call('read_rows',{'source':'grades'})['rows'],d['grades'])
    def test_correct_answer_without_reads_is_not_answer_failure(self):
        e,d=self.make('coverage');e.call('write_submission',{'rows_json':json.dumps(oracle(d))});e.call('finish',{})
        s=e.score();self.assertTrue(s['answer_success']);self.assertTrue(s['success']);self.assertFalse(s['coverage_complete'])
    def test_wrong_and_duplicate_answer_rejected(self):
        e,d=self.make('clean');rows=oracle(d);rows[0]=rows[1];e.call('write_submission',{'rows_json':json.dumps(rows)});e.call('finish',{})
        self.assertFalse(e.score()['answer_success'])
    def test_zero_and_unpublished_versions(self):
        d=dataset(1)
        for r in d['enrollment']:r['status']='active' if r['student_id']=='s01' else 'inactive'
        for r in d['grades']:
            if r['student_id']=='s01' and r['batch_id']=='B2':r['score']=0
        self.assertEqual(oracle(d)[0][2],0);self.assertEqual(answer_rows(d),oracle(d))
        d=dataset(1)
        for r in d['grades']:
            if r['record_id']=='g-B2-s02-r2':r['published']=False
        self.assertEqual(oracle(d)[0][0],'s02');self.assertEqual(answer_rows(d),oracle(d))

if __name__=='__main__':unittest.main()
