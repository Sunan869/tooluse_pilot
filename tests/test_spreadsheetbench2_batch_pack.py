"""Offline tests for Chinese Prompt + standalone batch files; no model API."""
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_batch_pack import pack,selftest,PROMPT_ZH
from spreadsheetbench2_case_validate import validate
from spreadsheetbench2_discovery_factory import PROMPT

DATA=Path("runs/ssb2-discovered-v2")

class PublicContract(unittest.TestCase):
    def test_both_prompts_are_chinese_and_no_solution_leak(self):
        self.assertIn("人为引入",PROMPT_ZH)
        self.assertIn("只恢复本题",PROMPT_ZH)
        self.assertIn("output/input.xlsx",PROMPT_ZH)
        self.assertIn("只恢复本次人为改动",PROMPT)
        for clue in ("Q23","K80","=Q43*Q17","=K79*$J$76"):
            self.assertNotIn(clue,PROMPT_ZH)
            self.assertNotIn(clue,PROMPT)

@unittest.skipUnless((DATA/"private"/"oracle.json").is_file(),
                     "Requires locally generated 136-case dataset")
class RealBatchTests(unittest.TestCase):
    def test_case_layout_golden_negative_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp)/"batch"
            result=pack(DATA,output,limit=2)
            self.assertEqual(result["case_count"],2)
            manifest=json.loads((output/"batch_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["case_count"],2)
            for item in manifest["cases"]:
                case=output/item["path"]
                for rel in ("prompt.md","input.xlsx","metadata.json",
                            "private/answer.xlsx","private/oracle.json","private/validate.py"):
                    self.assertTrue((case/rel).is_file(),rel)
                meta=json.loads((case/"metadata.json").read_text(encoding="utf-8"))
                self.assertEqual(meta["language"],"zh-CN")
                self.assertNotIn("faults",meta)
                self.assertNotIn("original_formula",meta)
                self.assertTrue(validate(case,case/"private"/"answer.xlsx")["pass"])
                self.assertFalse(validate(case,case/"input.xlsx")["pass"])
            report=selftest(output)
            self.assertEqual(report["positive_negative_passed"],2)
            self.assertFalse(report["failures"])
            with self.assertRaises(FileExistsError):
                pack(DATA,output,limit=1)

if __name__=="__main__":
    unittest.main()
