import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.enterprise_v2 import generate,reference
from tooluse_pilot.failure_mutations import variants,evaluate,create,verify

class MutationTests(unittest.TestCase):
    def test_counterfactual_paths(self):
        for seed in range(8):
            base=generate(seed,8)
            checked=evaluate(base)
            self.assertEqual(len(checked),2)
            self.assertNotEqual(checked[0][1]["settled_ids"],checked[1][1]["settled_ids"])
            self.assertTrue(all(reference(c)["success"] for c,_ in checked))

    def test_materialize_and_reverify(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            source=root/"base.json"
            source.write_text(json.dumps(generate(7,8)),encoding="utf-8")
            result=create(source,root/"output")
            self.assertEqual(result["generated"],2)
            self.assertTrue(verify(root/"output")["verified"])

    def test_no_input_mutation(self):
        base=generate(2,8)
        before=json.dumps(base,sort_keys=True)
        list(variants(base))
        self.assertEqual(before,json.dumps(base,sort_keys=True))
