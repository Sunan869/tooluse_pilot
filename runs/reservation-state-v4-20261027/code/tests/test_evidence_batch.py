import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.evidence_batch import generate_pair,verify
class EvidenceBatchTests(unittest.TestCase):
    def test_pairs(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"cases"
            self.assertEqual(generate_pair(p,3)["candidate_count"],6)
            self.assertTrue(verify(p)["verified"])
