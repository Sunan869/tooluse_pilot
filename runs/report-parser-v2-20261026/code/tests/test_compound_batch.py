import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.compound_batch import batch,verify

class CompoundBatchTests(unittest.TestCase):
    def test_batch(self):
        with tempfile.TemporaryDirectory() as td:
            folder=Path(td)/"batch"
            self.assertEqual(batch(folder,5)["count"],5)
            self.assertTrue(verify(folder)["verified"])
