import unittest
from tooluse_pilot.state_profiles import StateProfile,PROFILES,reference,mutant

class ProfilesTests(unittest.TestCase):
    def test_all_profiles(self):
        for profile in PROFILES:
            for seed in range(20):
                self.assertTrue(reference(profile,seed)["success"],(profile,seed))
                self.assertFalse(mutant(profile,seed)["success"],(profile,seed))
    def test_multi_source_really_requires_cross_source(self):
        env=StateProfile(0,"multi_source")
        env.call("read_order",{})
        latest=env.call("read_order",{})["order"]
        env.call("settle_order",latest)
        self.assertFalse(env.score()["success"])
        env.call("read_replica",{})
        self.assertTrue(env.score()["success"])

    def test_repeated_settle_is_not_success(self):
        env=StateProfile(0,"implicit")
        env.call("read_order",{})
        latest=env.call("read_order",{})["order"]
        env.call("settle_order",latest)
        env.call("settle_order",latest)
        self.assertFalse(env.score()["success"])

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
