import unittest
from tooluse_pilot.state_profiles import StateProfile,PROFILES,reference,mutant

class ProfilesTests(unittest.TestCase):
    def test_all_profiles(self):
        for profile in PROFILES:
            for seed in range(20):
                self.assertTrue(reference(profile,seed)["success"],(profile,seed))
                self.assertFalse(mutant(profile,seed)["success"],(profile,seed))
    def test_silent_update(self):
        env=StateProfile(0,"implicit")
        self.assertNotIn("notice",env.call("read_order",{}))
        self.assertEqual(env.call("read_order",{})["order"]["version"],env.state["updated_version"])
    def test_concurrent_collision(self):
        env=StateProfile(0,"concurrent")
        env.call("read_order",{})
        old=env.call("read_order",{})["order"]
        self.assertFalse(env.call("settle_order",old)["ok"])
        new=env.call("read_order",{})["order"]
        self.assertTrue(env.call("settle_order",new)["ok"])
        self.assertTrue(env.score()["success"])
