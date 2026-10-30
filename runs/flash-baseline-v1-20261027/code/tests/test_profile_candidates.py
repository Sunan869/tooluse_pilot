import json
import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.profile_candidates import make_profiles,verify_profiles
from tooluse_pilot.state_profiles import StateProfile
from tooluse_pilot.research import generate

class ProfileCandidateTests(unittest.TestCase):
    def test_generate_verify(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/"profiles"
            out=make_profiles(root,range(3))
            self.assertEqual(out["count"],9)
            self.assertTrue(verify_profiles(root)["verified"])
            sample=json.loads((root/"state_change-concurrent-0"/"candidate.json").read_text(encoding="utf-8"))
            env=StateProfile(sample,sample["profile"])
            env.call("read_order",{})
            first=env.call("read_order",{})["order"]
            self.assertFalse(env.call("settle_order",first)["ok"])
            current=env.call("read_order",{})["order"]
            self.assertTrue(env.call("settle_order",current)["ok"])
            self.assertTrue(env.score()["success"])

if __name__=="__main__":unittest.main()
