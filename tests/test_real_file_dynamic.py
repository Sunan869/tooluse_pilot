import tempfile,shutil,unittest
from pathlib import Path
from tooluse_pilot.real_file_dynamic import generate,reference,Environment
class DynamicFileTests(unittest.TestCase):
    def test_reference_all_seeds(self):
        for seed in range(10):
            with tempfile.TemporaryDirectory() as temp:
                source=Path(temp)/"source";case=generate(seed,source)
                prior=(source/"procurement.xlsx").read_bytes()
                dest=Path(temp)/"working";shutil.copytree(source,dest)
                self.assertTrue(reference(case,dest)["success"])
                self.assertEqual(prior,(source/"procurement.xlsx").read_bytes())
    def test_skip_initial_files_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(1,p);e=Environment(case,p)
            with self.assertRaises(ValueError):e.call("receive_update",{})
            e.close()
