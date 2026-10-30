import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.research import FAMILIES, generate, make_batch, validate, verify_batch


class ResearchTests(unittest.TestCase):
    def test_all_families(self):
        for family in FAMILIES:
            case = generate(family, 7)
            self.assertTrue(validate(case)["mutant_rejected"])

    def test_determinism(self):
        for family in FAMILIES:
            self.assertEqual(generate(family, 21), generate(family, 21))
            self.assertNotEqual(generate(family, 21), generate(family, 22))

    def test_batch_and_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "batch"
            summary = make_batch(root, range(4))
            self.assertEqual(summary["count"], 12)
            self.assertEqual(verify_batch(root)["count"], 12)
            p = root / "state_change-0" / "candidate.json"
            obj = json.loads(p.read_text(encoding="utf-8"))
            obj["oracle"]["settle_amount"] = -1
            p.write_text(json.dumps(obj), encoding="utf-8")
            with self.assertRaises(ValueError):
                verify_batch(root)


if __name__ == "__main__":
    unittest.main()
