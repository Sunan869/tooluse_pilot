"""Offline validation of financial invariants and independent numeric witnesses."""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_fault_factory import workbook
from spreadsheetbench2_financial_constraints import (
    eval_excel,verify_formula,known_rules,evaluate_business_constraints,
    classify_extra_business_rule,supplemental_lbo_rules,UnsupportedExpression)

ROOT=Path(os.getenv("SSB2_MUTATION_ROOT","runs/ssb2-injected-01"))
BASE=ROOT/"private"/"normalized_baseline.xlsx"
GPT=Path(os.getenv("SSB2_GPT_OUTPUT","runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx"))

class InterpreterTests(unittest.TestCase):
    def test_limited_formula_parser(self):
        inputs={("x","A1"):2,("x","A2"):3,("x","B1"):5}
        self.assertEqual(eval_excel("=SUM(A1:A2)+B1","x",inputs),10)
        self.assertEqual(eval_excel("=A1+A2+B1","x",inputs),10)
        with self.assertRaises(UnsupportedExpression):
            eval_excel("=SUM(A1:A100)","x",inputs)

@unittest.skipUnless(ROOT.is_dir() and BASE.is_file(),"Requires locally generated 56-task dataset")
class BusinessWitnessIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book=workbook(BASE)
        cls.rules=known_rules(cls.book)
        cls.cases=json.loads((ROOT/"private"/"oracle.json").read_text(encoding="utf-8"))

    def test_32_source_formula_positive_and_injected_negative(self):
        self.assertEqual(len(self.rules),32)
        for (sheet,addr),rule in self.rules.items():
            with self.subTest(cell=f"{sheet}!{addr}"):
                self.assertEqual(verify_formula(rule["correct"],rule)["status"],"pass")
                damaged=verify_formula(rule["mutated"],rule)
                self.assertEqual(damaged["status"],"fail")
                self.assertTrue(damaged["counterexamples"])

    def test_mathematically_equivalent_repair_not_rejected(self):
        rule=self.rules[("Ex 4 - Organic Operating Model","E40")]
        self.assertEqual(verify_formula("=E28-E31-E32",rule)["status"],"pass")
        revenue=self.rules[("Ex 4 - Organic Operating Model","D18")]
        self.assertEqual(verify_formula("=D16+D17",revenue)["status"],"pass")
        self.assertEqual(verify_formula("=SUM(A1:A50)",revenue)["status"],"unverified")

    def test_all_56_baseline_good_and_mutant_bad(self):
        self.assertEqual(len(self.cases),56)
        for task in self.cases:
            with self.subTest(case=task["id"]):
                good=evaluate_business_constraints(ROOT,task,BASE)
                bad=evaluate_business_constraints(ROOT,task,ROOT/task["input_path"])
                self.assertEqual(good["pass"],len(task["faults"]))
                self.assertEqual(good["fail"],0)
                self.assertEqual(bad["fail"],len(task["faults"]))
                self.assertEqual(bad["unverified"],0)

    @unittest.skipUnless(GPT.is_file(),"Requires prior GPT-0033 output")
    def test_gpt0033_business_and_supplemental_witness(self):
        task=next(case for case in self.cases if case["id"]=="SSB2-MUT-0033")
        result=evaluate_business_constraints(ROOT,task,GPT)
        self.assertEqual((result["pass"],result["fail"],result["unverified"]),(1,1,0))
        gpt=workbook(GPT)
        self.assertEqual(len(supplemental_lbo_rules()),6)
        for (sheet,cell) in supplemental_lbo_rules():
            with self.subTest(cell=f"{sheet}!{cell}"):
                source=self.book["cells"][sheet][cell]["formula"]
                submitted=gpt["cells"][sheet][cell]["formula"]
                evidence=classify_extra_business_rule(sheet,cell,source,submitted)
                self.assertEqual(evidence["baseline_status"],"fail")
                self.assertEqual(evidence["submission_status"],"pass")

if __name__=="__main__":unittest.main()
