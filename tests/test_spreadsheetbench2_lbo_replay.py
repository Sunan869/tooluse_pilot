"""Offline five-year LBO cash-flow/debt/exit regression; no model API usage."""
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_lbo_replay import (
    FormulaEngine, cases, replay_formula, summary, compare_books,
    independent_ledger)
from spreadsheetbench2_fault_factory import workbook
from spreadsheetbench2_financial_constraints import UnsupportedExpression

DATASET=Path(os.getenv('SSB2_MUTATION_ROOT','runs/ssb2-injected-01'))
BASELINE=Path(os.getenv('SSB2_LBO_BASELINE',
                         str(DATASET/'private'/'normalized_baseline.xlsx')))
SUBMISSION=Path(os.getenv('SSB2_GPT_OUTPUT',
                           'runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx'))


@unittest.skipUnless(BASELINE.is_file() and SUBMISSION.is_file(),
                     'Requires local dataset and GPT-0033 workbook; no API used')
class LboReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=workbook(BASELINE)
        cls.gpt=workbook(SUBMISSION)
        cls.report=compare_books(BASELINE,SUBMISSION)

    def test_five_years_and_circular_fee_convergence(self):
        for case in cases():
            with self.subTest(case=case.name):
                a=replay_formula(self.original,case)
                b=replay_formula(self.gpt,case)
                self.assertEqual(len(a['years']),5)
                self.assertEqual(len(b['years']),5)
                self.assertTrue(all(y['fee_converged'] for y in a['years']))
                self.assertTrue(all(y['fee_converged'] for y in b['years']))
                self.assertTrue(all(y['fee_residual']<1e-7 for y in b['years']))

    def test_mandatory_repayment_and_ma_off_reveal_model_defects(self):
        cases_by_name={x['case']:x for x in self.report['cases']}
        self.assertGreaterEqual(cases_by_name['mandatory_amort']['reference']['hard_failure_count'],4)
        self.assertEqual(cases_by_name['mandatory_amort']['submission']['hard_failure_count'],0)
        self.assertGreaterEqual(cases_by_name['ma_off']['reference']['policy_alert_count'],10)
        self.assertEqual(cases_by_name['ma_off']['submission']['policy_alert_count'],0)
        self.assertGreater(cases_by_name['entry_revolver_funded']['reference']['hard_failure_count'],0)
        self.assertEqual(cases_by_name['entry_revolver_funded']['submission']['hard_failure_count'],0)

    def test_stressed_liquidity_not_overstated_as_success(self):
        cases_by_name={x['case']:x for x in self.report['cases']}
        for name in ('negative_cash','low_cash'):
            with self.subTest(scenario=name):
                self.assertGreater(cases_by_name[name]['submission']['policy_alert_count'],0)
                self.assertGreater(cases_by_name[name]['submission_vs_independent_policy']['years_with_differences'],0)

    def test_cash_retention_is_explicit_hypothesis(self):
        for case in cases():
            reference=independent_ledger(case)
            self.assertTrue(reference['cash_policy_is_hypothetical'])
            self.assertEqual(len(reference['years']),5)
        s=summary(self.report)
        self.assertEqual(s['scenario_count'],9)
        self.assertEqual(s['unverified_count'],0)
        self.assertTrue(s['fee_solver_all_cases_converged'])

    def test_formula_interpreter_rejects_arbitrary_python(self):
        engine=FormulaEngine(self.original,{})
        with self.assertRaises(UnsupportedExpression):
            engine.evaluate('=INDIRECT("A1")',"Ex 1 - LBO")
        with self.assertRaises(UnsupportedExpression):
            engine.evaluate('=A1.__class__',"Ex 1 - LBO")


if __name__=='__main__':
    unittest.main()
