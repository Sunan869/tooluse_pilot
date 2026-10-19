import unittest,tempfile,json
from pathlib import Path
from tooluse_pilot.hard import make_hard_case,reference_hard
from tooluse_pilot.grade import grade

class HardTests(unittest.TestCase):
    def test_reference_and_corrupt(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'case';make_hard_case(root,42,85)
            reference_hard(root)
            score=grade(root,root/'trace.json')
            self.assertEqual(score['total'],100,score)
            f=root/'output'/'anomalies.csv'
            lines=f.read_text().splitlines()
            f.write_text('\n'.join(lines[:-1])+'\n')
            self.assertLess(grade(root,root/'trace.json')['total'],100)
    def test_dynamic_revision(self):
        from tooluse_pilot.hard import oracle
        from tooluse_pilot.xlsx import read_sheets
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case";make_hard_case(root,42,85,dynamic=True)
            rows=read_sheets(root/"input"/"procurement.xlsx")
            baseline=json.loads((root/"private"/"oracle.json").read_text())["rows"]
            revised=json.loads((root/"private"/"oracle_revised.json").read_text())["rows"]
            self.assertEqual(baseline,oracle(rows))
            self.assertEqual(revised,oracle(rows,"2026-09-11"))
            self.assertNotEqual(baseline,revised)
            reference_hard(root)
            self.assertEqual(grade(root,root/"trace.json")["result_score"],1)
            (root/"private"/"revision_applied.json").write_text('{"applied":true}')
            self.assertLess(grade(root,root/"trace.json")["result_score"],1)

    def test_two_phase_delta_rejects_stale(self):
        from tooluse_pilot.grade import delta_score
        from tooluse_pilot.hard import oracle
        from tooluse_pilot.tools import StructuredTools
        from tooluse_pilot.xlsx import read_sheets
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "case"
            make_hard_case(root, 42, 85, dynamic=True)
            reference_hard(root)
            (root / "private" / "revision_applied.json").write_text('{"applied":true}')
            score = delta_score(root)
            self.assertGreater(score["changed_count"], 0)
            self.assertLess(score["changed_accuracy"], 1)
            revised = json.loads((root / "private" / "oracle_revised.json").read_text())["rows"]
            StructuredTools(root).write_csv(revised)
            self.assertEqual(delta_score(root)["changed_accuracy"], 1.0)
            # A partial update must not pass.
            StructuredTools(root).write_csv(revised[:-1])
            self.assertLess(delta_score(root)["changed_accuracy"], 1)

    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'a';b=Path(td)/'b'
            make_hard_case(a,44,40);make_hard_case(b,44,40)
            self.assertEqual((a/'private'/'oracle.json').read_bytes(),(b/'private'/'oracle.json').read_bytes())
if __name__=='__main__':unittest.main()
