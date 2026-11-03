"""Offline tests for source-traced LBO driver inputs and scenario matrix."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_financial_constraints import UnsupportedExpression
from spreadsheetbench2_fault_factory import workbook
from spreadsheetbench2_real_drivers import (
    RealDriverEvaluator, derive_case, compare_actual_drivers,
    replay_real_driver_matrix)

ROOT=Path(os.getenv('SSB2_MUTATION_ROOT','runs/ssb2-injected-01'))
BASE=Path(os.getenv('SSB2_REAL_BASELINE',str(ROOT/'private'/'normalized_baseline.xlsx')))
GPT=Path(os.getenv('SSB2_GPT_OUTPUT','runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx'))


class RestrictedDriverInterpreterTests(unittest.TestCase):
    def setUp(self):
        def n(value=None,formula=None):
            return {'formula':formula,'value':None if value is None else str(value),
                    'type':None,'formula_attrs':{}}
        self.book={'cells':{'Toy':{
            'A1':n(2),'A2':n(3),'C1':n(2),
            'B1':n(formula='=CHOOSE($C$1,A1,A2)'),
            'D1':n(formula='=SUM(A1:A2)'),
            'E1':n(formula='=AVERAGE(A1:A2)'),
            'F1':n(formula='=INDEX(A1:A2,MATCH(3,A1:A2,0))'),
            'G1':n(formula='=A1*(1+2.5%)'),
            'H1':n(formula='=H1+1'),
            'I1':n(formula='=__import__("os").system("echo BAD")'),
            'J1':n(formula='=CHOOSE(1,A2,H1)'),
            'K1':n(formula='=SUM(A1:A2)+1')
        }}}

    def test_supported_math_choices_and_index(self):
        e=RealDriverEvaluator(self.book)
        self.assertEqual(e.number('Toy','B1'),3)
        self.assertEqual(e.number('Toy','D1'),5)
        self.assertEqual(e.number('Toy','E1'),2.5)
        self.assertEqual(e.number('Toy','F1'),3)
        self.assertAlmostEqual(e.number('Toy','G1'),2.05)
        self.assertEqual(e.number('Toy','J1'),3)
        self.assertEqual(e.number('Toy','K1'),6)

    def test_unsupported_and_cycle_fail_closed(self):
        e=RealDriverEvaluator(self.book)
        with self.assertRaises(UnsupportedExpression):e.number('Toy','I1')
        with self.assertRaises(UnsupportedExpression):e.number('Toy','H1')
        with self.assertRaises(UnsupportedExpression):e.evaluate('=INDIRECT("A1")','Toy')


@unittest.skipUnless(BASE.is_file() and GPT.is_file(),
                     'Requires 01_01 normalized baseline and GPT-0033 output')
class RealWorkbookIntegrationTests(unittest.TestCase):
    def test_source_model_hash_and_default_selectors(self):
        import hashlib
        self.assertEqual(hashlib.sha256(BASE.read_bytes()).hexdigest(),
                         '3651abc8dc82ccf99257e28c285ee2f9fefcac97f553423ff8d359908cd80090')
        book=workbook(BASE)
        self.assertEqual(int(book['cells']['Ex 1 - LBO']['C9']['value']),1)
        self.assertEqual(int(book['cells']['Ex 1 - LBO']['C10']['value']),1)
        self.assertEqual(int(book['cells']['Ex 5 - M&A']['C4']['value']),3)

    def test_actual_base_inputs_have_financial_provenance(self):
        case,trace=derive_case(BASE)
        self.assertAlmostEqual(case.fcf[0],591.368432424,places=5)
        self.assertAlmostEqual(case.ebitda[0],780.252771933,places=5)
        self.assertAlmostEqual(case.sofr[0],0.0331833333333,places=10)
        self.assertEqual(case.acq_debt,(0.,)*5)
        self.assertGreater(trace['provenance_cells_visited'],500)
        self.assertTrue(any('Opening_cash_is_assumed_zero' in x for x in trace['warnings']))

    def test_operating_and_acquisition_switches_are_distinct(self):
        active,_=derive_case(BASE,operating_case=1,ma_case=1,ma_switch=1)
        disabled,_=derive_case(BASE,operating_case=1,ma_case=1,ma_switch=0)
        empty,_=derive_case(BASE,operating_case=1,ma_case=3,ma_switch=0)
        self.assertGreater(active.acq_debt[1],0)
        self.assertEqual(active.acq_debt,disabled.acq_debt)
        self.assertTrue(all(abs(a-b)<1e-8 for a,b in zip(disabled.fcf,empty.fcf)))
        self.assertGreater(active.fcf[1],disabled.fcf[1])

    def test_changed_upstream_drivers_are_not_hidden(self):
        comparison=compare_actual_drivers(BASE,GPT,operating_case=2,ma_case=3,ma_switch=1)
        self.assertIn('fcf',comparison['driver_differences'])
        self.assertEqual(len(comparison['driver_differences']['fcf']),5)
        same=compare_actual_drivers(BASE,GPT,operating_case=1,ma_case=3,ma_switch=1)
        self.assertFalse(same['driver_differences'])

    def test_18_real_control_combinations(self):
        result=replay_real_driver_matrix(BASE,GPT)
        self.assertEqual((result['scenario_count'],result['evaluated_count'],result['unverified_count']),
                         (18,18,0))
        self.assertEqual((result['baseline_total_hard_failures'],
                          result['submission_common_drivers_total_hard_failures'],
                          result['submission_own_drivers_total_hard_failures']),(5,0,0))
        self.assertEqual(result['scenario_count_with_changed_upstream_drivers'],12)
        self.assertTrue(result['all_converged'])
        self.assertTrue(all('reference_case_values' in x for x in result['scenarios']))


if __name__=='__main__':
    unittest.main()
