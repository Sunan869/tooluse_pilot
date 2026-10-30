import tempfile,unittest
from pathlib import Path
from tooluse_pilot.real_file_batch import make_batch,verify,stale_mutant
from tooluse_pilot.real_file_dynamic import generate

class RealFileBatchTests(unittest.TestCase):
    def test_batch_reference_and_mutant(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/"cases"
            result=make_batch(out)
            self.assertEqual(result["count"],3)
            self.assertEqual(result["distinct_final_winners"],3)
            self.assertTrue(verify(out)["verified"])
    def test_obsolete_answer_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"one"
            case=generate(0,root)
            result=stale_mutant(case,root)
            self.assertFalse(result["success"])
            self.assertFalse(result["checks"]["result"])
    def test_refuse_existing_destination(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(FileExistsError):make_batch(Path(td))
