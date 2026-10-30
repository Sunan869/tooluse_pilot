import sys,unittest,tempfile,json
from pathlib import Path
ROOT=Path(__file__).resolve().parent;sys.path.insert(0,str(ROOT/'code'))
from w9_data import create
from independent_graph import oracle
from tooluse_pilot.w9_task import Environment
class Tests(unittest.TestCase):
 def make(self,c):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);p=Path(t.name)/'c';case,data=create(p,c);return Environment(case,p),data
 def test_oracle_all_valid_paths(self):
  e,d=self.make('permanent');self.assertEqual(oracle(d,'transient')['minimum_cost'],3);o=oracle(d,'permanent');self.assertEqual({tuple(p['path']) for p in o['optimal_paths']},{('a1','a3'),('b1','b2')})
 def test_identical_initial_failure_no_effect(self):
  a,d=self.make('transient');b,_=self.make('permanent');before=a.call('get_package',{});x=a.call('send_leg',{'route_id':'direct'});y=b.call('send_leg',{'route_id':'direct'});self.assertEqual(x,y);self.assertEqual(x['code'],'E503');self.assertEqual(before,a.call('get_package',{}));self.assertEqual(a.call('get_ledger',{})['charges'],[])
 def test_transient_retry_and_duplicate_no_charge(self):
  e,d=self.make('transient');e.call('send_leg',{'route_id':'direct'});self.assertEqual(e.call('inspect_incident',{'incident_id':'I001'})['status'],'resolved');self.assertTrue(e.call('send_leg',{'route_id':'direct'})['success']);self.assertFalse(e.call('send_leg',{'route_id':'direct'})['success']);e.call('finish',{});self.assertTrue(e.score()['success']);self.assertEqual(e.score()['actual_cost'],3)
 def test_both_permanent_recovery_routes(self):
  for path in [('a1','a3'),('b1','b2')]:
   e,d=self.make('permanent');e.call('send_leg',{'route_id':'direct'});self.assertEqual(e.call('inspect_incident',{'incident_id':'I001'})['status'],'permanent_for_episode')
   for route in path:self.assertTrue(e.call('send_leg',{'route_id':route})['success'])
   e.call('finish',{});self.assertTrue(e.score()['success'])
 def test_missed_connection_recoverable(self):
  e,d=self.make('permanent');e.call('send_leg',{'route_id':'a1'});r=e.call('send_leg',{'route_id':'a2'});self.assertEqual(r['code'],'MISSED_DEPARTURE');e.call('send_leg',{'route_id':'a3'});e.call('finish',{});self.assertTrue(e.score()['success']);self.assertFalse(e.score()['fault_exposed'])
 def test_no_exposure_and_suboptimal_separate(self):
  e,d=self.make('transient');e.call('send_leg',{'route_id':'b1'});e.call('send_leg',{'route_id':'b2'});e.call('finish',{});s=e.score();self.assertTrue(s['checks']['arrived']);self.assertFalse(s['checks']['minimum_cost']);self.assertFalse(s['fault_exposed'])
 def test_reads_future_hubs_do_not_advance_time(self):
  e,d=self.make('permanent');p=e.call('get_package',{});r=e.call('list_routes',{'origin':'A'});self.assertTrue(r['complete']);self.assertEqual(len(r['routes']),2);self.assertEqual(e.call('get_package',{}),p)
if __name__=='__main__':unittest.main()
