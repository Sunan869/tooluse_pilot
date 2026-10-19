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
    def test_reproducible(self):
        with tempfile.TemporaryDirectory() as td:
            a=Path(td)/'a';b=Path(td)/'b'
            make_hard_case(a,44,40);make_hard_case(b,44,40)
            self.assertEqual((a/'private'/'oracle.json').read_bytes(),(b/'private'/'oracle.json').read_bytes())
if __name__=='__main__':unittest.main()
