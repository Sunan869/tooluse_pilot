import unittest
from tooluse_pilot.compound import generate,CompoundEnvironment,reference,mutant
class CompoundTests(unittest.TestCase):
    def test_reference_and_mutants(self):
        for seed in range(30):
            case=generate(seed)
            self.assertTrue(reference(case)["success"],seed)
            self.assertFalse(mutant(case)["success"],seed)
    def test_duplicate_charge_rejected(self):
        e=CompoundEnvironment(generate(0))
        e.call("read_replica",{})
        p=e.call("read_primary",{})["order"]
        e.call("settle",{"version":p["version"],"amount":p["amount"],"key":"key1"})
        p=e.call("read_primary",{})["order"]
        self.assertTrue(e.call("settle",{"version":p["version"],"amount":p["amount"],"key":"key1"})["ok"])
        self.assertTrue(e.call("settle",{"version":p["version"],"amount":p["amount"],"key":"key1"})["deduplicated"])
        self.assertEqual(e.score()["successful_settlements"],1)
        self.assertFalse(e.call("settle",{"version":p["version"],"amount":p["amount"],"key":"newkey"})["ok"])
        self.assertFalse(e.score()["success"])
