"""Offline checks for blind-case isolation, hashes, and task wording."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
from spreadsheetbench2_blind_case import create, filehash, INSTRUCTION

class BlindCaseTests(unittest.TestCase):
    def test_source_immutability_and_oracle_isolation(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"source"
            (source/"input").mkdir(parents=True)
            (source/"private").mkdir()
            original=source/"input"/"sample.xlsx"
            original.write_bytes(b"sample workbook bytes for isolation contract")
            oracle={"kind":"minimal_repair","source_sha256":filehash(original),
                    "expected_formulas":{f"X{i}":"=SUM(A1:A3)" for i in range(16)}}
            (source/"private"/"oracle.json").write_text(json.dumps(oracle),encoding="utf-8")
            before=filehash(original)
            dest=root/"blind"
            result=create(source,dest)
            self.assertEqual(result["input_sha256"],before)
            self.assertEqual(filehash(original),before)
            self.assertEqual(filehash(dest/"input"/"sample.xlsx"),before)
            self.assertTrue((dest/"private"/"oracle.json").is_file())
            self.assertFalse((dest/"output"/"oracle.json").exists())
            prompt=(dest/"instruction.md").read_text(encoding="utf-8")
            self.assertEqual(prompt,INSTRUCTION)
            for leaked in ("D42","M&A","SUM(D36","16_known"):
                self.assertNotIn(leaked,prompt)
            with self.assertRaises(FileExistsError):
                create(source,dest)

    def test_hash_guard(self):
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/"source"
            (source/"input").mkdir(parents=True)
            (source/"private").mkdir()
            (source/"input"/"x.xlsx").write_bytes(b"a")
            (source/"private"/"oracle.json").write_text(json.dumps({
                "kind":"minimal_repair","source_sha256":"incorrect",
                "expected_formulas":{f"X{i}":"x" for i in range(16)}}),encoding="utf-8")
            with self.assertRaises(ValueError):
                create(source,Path(td)/"bad")
if __name__=="__main__":
    unittest.main()
