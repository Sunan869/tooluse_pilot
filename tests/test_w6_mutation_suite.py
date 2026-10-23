import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.real_file_dynamic import generate
from tooluse_pilot.w6_mutation_suite import verify_batch,MUTANTS

class W6MutationTests(unittest.TestCase):
    def test_all_mutants_rejected_across_distinct_winners(self):
        with tempfile.TemporaryDirectory() as td:
            paths=[]
            for seed in range(3):
                path=Path(td)/str(seed)
                generate(seed,path)
                paths.append(path)
            result=verify_batch(paths)
            self.assertEqual(result["verified_cases"],3)
            self.assertEqual(result["mutants_per_case"],9)
            for row in result["cases"]:
                self.assertTrue(row["reference_passed"])
                self.assertEqual(row["mutants_rejected"],len(MUTANTS))
    def test_stage_specific_failures_identifiable(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"case"
            generate(0,path)
            result=verify_batch([path])
            errors=result["cases"][0]["mutants"]
            self.assertFalse(errors["stale_workbook"]["result"])
            self.assertFalse(errors["stale_report"]["report"])
            self.assertFalse(errors["wrong_count"]["result"])
            self.assertFalse(errors["wrong_vendor"]["result"])
            self.assertFalse(errors["wrong_requirements"]["requirements"])
            self.assertFalse(errors["contradictory_report"]["report"])
