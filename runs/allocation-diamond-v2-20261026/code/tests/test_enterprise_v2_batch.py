import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.enterprise_v2_batch import make_batch,verify
class EnterpriseV2BatchTests(unittest.TestCase):
    def test_batch(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/"v2"
            self.assertEqual(make_batch(p,4,8)["count"],4)
            self.assertTrue(verify(p)["verified"])
