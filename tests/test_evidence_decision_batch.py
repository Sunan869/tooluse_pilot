import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.evidence_decision_batch import make_batch,verify
class DecisionBatchTests(unittest.TestCase):
    def test_batch(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"batch"
            self.assertEqual(make_batch(root,2)["count"],12)
            self.assertTrue(verify(root)["verified"])
