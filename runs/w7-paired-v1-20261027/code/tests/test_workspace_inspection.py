import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.real_file_dynamic import generate, reference
from tooluse_pilot.failure_attribution import inspect_workspace

class InspectionTests(unittest.TestCase):
    def test_reference_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'case'
            case=generate(0,root)
            self.assertTrue(reference(case,root)['success'])
            self.assertTrue(inspect_workspace(root)['artifact_consistent'])

    def test_unedited_file_does_not_pass(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/'case'
            generate(0,root)
            self.assertFalse(inspect_workspace(root)['artifact_consistent'])
