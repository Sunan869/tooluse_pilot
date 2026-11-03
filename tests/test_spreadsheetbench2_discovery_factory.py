"""Regression for source-grounded 18-mechanism fault discovery, no model API."""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_discovery_factory import (
    LBO, PF, ORG, MA, PROMPT, make_cases, rulebook, witness, score, load_case)
from spreadsheetbench2_fault_factory import workbook

BASE=Path("runs/ssb2-injected-01/private/normalized_baseline.xlsx")
OUT=Path("runs/ssb2-discovered-v2")

class MetadataTests(unittest.TestCase):
    def test_prompt_does_not_leak_answer(self):
        for leak in ("E40","row 42","K80","Ex 5 - M&A","debt consideration",
                     "wrong reference","18 errors","88 sites"):
            self.assertNotIn(leak,PROMPT)
        self.assertIn("output/",PROMPT)

@unittest.skipUnless(BASE.is_file(),"Requires previously generated normalized baseline")
class DiscoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules=rulebook(workbook(BASE))

    def test_88_source_verified_sites_and_18_distinct_mechanisms(self):
        self.assertEqual(len(self.rules),88)
        self.assertEqual(len({r["mechanism"] for r in self.rules}),18)
        self.assertEqual(len({(r["sheet"],r["cell"]) for r in self.rules}),88)
        self.assertEqual({r["sheet"] for r in self.rules},{LBO,PF,ORG,MA})

    def test_all_sites_have_non_equivalent_numeric_witnesses(self):
        for r in self.rules:
            with self.subTest(rule=r["mechanism"],cell=r["cell"]):
                result=witness(r)
                self.assertGreaterEqual(result["distinguishing_trials"],1)

    def test_48_compounds_cross_sheet_and_reproducible(self):
        x=make_cases(self.rules,48,20261103)
        y=make_cases(self.rules,48,20261103)
        self.assertEqual(len(x),136)
        self.assertEqual(
            [[(a["sheet"],a["cell"]) for a in group] for group in x],
            [[(a["sheet"],a["cell"]) for a in group] for group in y])
        for group in x[88:]:
            self.assertGreaterEqual(len({r["sheet"] for r in group}),2)
            self.assertEqual(len(group),len({r["mechanism"] for r in group}))

@unittest.skipUnless((OUT/"private"/"oracle.json").is_file(),
                     "Run discovery_factory generate first")
class GeneratedCasesTests(unittest.TestCase):
    def test_private_oracle_and_136_unique_public_cases(self):
        tasks=json.loads((OUT/"private"/"oracle.json").read_text(encoding="utf-8"))
        public=[json.loads(x) for x in (OUT/"public"/"tasks.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(tasks),136)
        self.assertEqual(len(public),136)
        self.assertEqual(len({x["input_sha256"] for x in tasks}),136)
        self.assertTrue(all("faults" not in x and "sheet" not in x and "correct" not in x for x in public))
        self.assertEqual(len([x for x in tasks if len(x["faults"])>1]),48)
        self.assertEqual(load_case(OUT,tasks[0]["id"])["id"],tasks[0]["id"])

    def test_first_and_last_cases_reject_unrepaired_input(self):
        baseline=OUT/"private"/"normalized_baseline.xlsx"
        tasks=json.loads((OUT/"private"/"oracle.json").read_text(encoding="utf-8"))
        for c in (tasks[0],tasks[-1]):
            with self.subTest(case=c["id"]):
                self.assertTrue(score(OUT,c,baseline)["pass"])
                self.assertFalse(score(OUT,c,OUT/c["input_path"])["pass"])

if __name__=="__main__":
    unittest.main()
