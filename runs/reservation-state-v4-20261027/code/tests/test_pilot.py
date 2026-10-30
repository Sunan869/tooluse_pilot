import csv, tempfile, unittest
from pathlib import Path
from tooluse_pilot.generate import make_case
from tooluse_pilot.reference import run
from tooluse_pilot.grade import grade
from tooluse_pilot.tools import StructuredTools

class PilotTests(unittest.TestCase):
    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            root=make_case(Path(d)/'case',seed=42,count=60)
            t=StructuredTools(root)
            self.assertEqual(set(t.list_sheets()),{'Orders','Payments','Suppliers','Rules'})
            self.assertEqual(len(t.read_rows('Orders',limit=10)),10)
            trace=run(root,'structured'); report=grade(root,trace)
            self.assertEqual(report['total'],100,report)
            run(root,'python_shell')
            self.assertEqual(grade(root)['result_score'],1)
            path=root/'output'/'anomalies.csv'
            with path.open(newline='',encoding='utf-8') as f:
                original=list(csv.DictReader(f))
            with path.open('w',newline='',encoding='utf-8') as f:
                w=csv.DictWriter(f,fieldnames=original[0]);w.writeheader();w.writerows(original[1:])
            self.assertLess(grade(root)['result_score'],1)
    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as d:
            a=make_case(Path(d)/'a',seed=11,count=35)
            b=make_case(Path(d)/'b',seed=11,count=35)
            self.assertEqual((a/'private/oracle.json').read_bytes(),(b/'private/oracle.json').read_bytes())
if __name__=='__main__':unittest.main()
