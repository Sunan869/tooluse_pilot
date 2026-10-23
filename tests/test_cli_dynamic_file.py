import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tooluse_pilot.cli import main
from tooluse_pilot.real_file_dynamic import generate

class DynamicFileCLITests(unittest.TestCase):
    def test_verify_dynamic_file_does_not_shadow_path(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)/"case"
            generate(0,root)
            before=(root/"procurement.xlsx").read_bytes()
            with patch("sys.argv",["tooluse-pilot","verify-dynamic-file",str(root)]):
                main()
            self.assertEqual(before,(root/"procurement.xlsx").read_bytes())
