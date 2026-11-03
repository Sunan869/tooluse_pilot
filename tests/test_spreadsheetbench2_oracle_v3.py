"""Focused offline regression tests for the three-axis injected-XLSX Oracle.

Use SSB2_MUTATION_ROOT and SSB2_GPT_OUTPUT for the real integration fixture.
No LLM, network, Excel/LibreOffice engine, or Golden is required to run tests.
"""
import json
import os
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
# For direct standalone testing before Git integration.
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from spreadsheetbench2_oracle_v3 import (
    additive_terms, compare_integrity, evaluate_v3, golden_correspondence)

ROOT=Path(os.getenv("SSB2_MUTATION_ROOT","runs/ssb2-injected-01"))
CASE="SSB2-MUT-0033"
OUTPUT=Path(os.getenv("SSB2_GPT_OUTPUT","runs/ssb2-fault-gpt-0033/output/Double Counting_mutated.xlsx"))
GOLDEN=Path(os.getenv("SSB2_GOLDEN","runs/ssb2-debugging-baseline/01_Debugging_01_01/private/01_golden.xlsx"))
REVIEW=Path(os.getenv("SSB2_REVIEW_EVIDENCE", "")) if os.getenv("SSB2_REVIEW_EVIDENCE") else None

class FormulaEvidenceTests(unittest.TestCase):
    def test_only_restricted_additive_equivalence(self):
        self.assertTrue(golden_correspondence("=SUM(Q85,Q76,Q65)","=+Q65+Q76+Q85"))
        self.assertFalse(golden_correspondence("=SUM(Q85,Q76,Q65,Q65)","=+Q65+Q76+Q85"))
        self.assertFalse(golden_correspondence("=Q65+2*Q76+Q85","=Q65+Q76+Q85"))
        self.assertIsNone(additive_terms("=SUM(A1:A9)"))

@unittest.skipUnless(ROOT.is_dir() and (ROOT/"private"/"oracle.json").is_file(),
                     "Requires locally generated fault-injection dataset")
class WorkbookIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data=json.loads((ROOT/"private"/"oracle.json").read_text(encoding="utf-8"))
        cls.task=next(item for item in cls.data if item["id"]==CASE)
        cls.baseline=ROOT/"private"/"normalized_baseline.xlsx"
        cls.injected=ROOT/cls.task["input_path"]

    def test_known_good_and_unmodified(self):
        good=evaluate_v3(ROOT,self.task,self.baseline)
        bad=evaluate_v3(ROOT,self.task,self.injected)
        self.assertTrue(good["pass"])
        self.assertEqual(good["injected_faults"]["fixed"],2)
        self.assertFalse(bad["pass"])
        self.assertEqual(bad["injected_faults"]["fixed"],0)
        self.assertTrue(bad["artifact_integrity"]["preservation_pass"])

    def test_all_56_positive_and_negative(self):
        for case in self.data:
            with self.subTest(case=case["id"]):
                good=evaluate_v3(ROOT,case,self.baseline)
                bad=evaluate_v3(ROOT,case,ROOT/case["input_path"])
                self.assertTrue(good["pass"])
                self.assertFalse(bad["pass"])
                self.assertEqual(bad["injected_faults"]["fixed"],0)

    def _tamper(self,part,cell,mutate):
        with tempfile.TemporaryDirectory() as td:
            candidate=Path(td)/"edited.xlsx"
            with zipfile.ZipFile(self.baseline) as src,zipfile.ZipFile(candidate,"w") as dest:
                for info in src.infolist():
                    data=src.read(info.filename)
                    if info.filename==part:
                        root=ET.fromstring(data)
                        ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                        node=root.find(f'.//m:sheetData/m:row/m:c[@r="{cell}"]',ns)
                        self.assertIsNotNone(node)
                        mutate(node,ns)
                        data=ET.tostring(root,encoding="utf-8",xml_declaration=True)
                    dest.writestr(info,data)
            yield candidate

    def test_style_damage_detected(self):
        for path in self._tamper("xl/worksheets/sheet4.xml","E40",lambda c,ns:c.set("s","999")):
            check=compare_integrity(self.injected,path)
            self.assertFalse(check["preservation_pass"])
            self.assertIn("cell_style_assignment_changed",check["issues"])

    def test_excel_data_table_damage_detected(self):
        def change(c,ns):
            f=c.find("m:f",ns)
            self.assertIsNotNone(f)
            self.assertEqual(f.attrib.get("t"),"dataTable")
            f.set("ref","AG18:AL22")
        for path in self._tamper("xl/worksheets/sheet1.xml","AG18",change):
            check=compare_integrity(self.injected,path)
            self.assertFalse(check["preservation_pass"])
            self.assertIn("array_or_data_table_formula_changed",check["issues"])

    @unittest.skipUnless(OUTPUT.is_file(),"Requires previous GPT-0033 result")
    def test_gpt0033_diagnostic(self):
        score=evaluate_v3(ROOT,self.task,OUTPUT,
                          golden=GOLDEN if GOLDEN.is_file() else None,
                          review_evidence=REVIEW if REVIEW is not None and REVIEW.is_file() else None)
        self.assertFalse(score["pass"])
        self.assertEqual(score["injected_faults"]["fixed"],1)
        self.assertIn("Ex 4 - Organic Operating Model!E40",score["injected_faults"]["not_repaired"])
        self.assertEqual(score["extra_changes"]["count"],45)
        self.assertTrue(score["artifact_integrity"]["preservation_pass"])
        if GOLDEN.is_file():
            self.assertEqual(score["extra_changes"]["evidence_tiers"].get("golden_correlated"),5)
        if REVIEW is not None and REVIEW.is_file():
            tiers=score["extra_changes"]["evidence_tiers"]
            self.assertEqual(tiers.get("plausible_unverified"),28)
            self.assertEqual(tiers.get("business_policy_pending"),12)

if __name__=="__main__":unittest.main()
