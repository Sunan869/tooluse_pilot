import tempfile
import unittest
from pathlib import Path
from tooluse_pilot.research import generate
from tooluse_pilot.workbook_task import create_workbook,read_region
from tooluse_pilot.executable import Environment

class WorkbookEnvironmentTests(unittest.TestCase):
    def test_real_workbook_and_distractor(self):
        for seed in range(8):
            with tempfile.TemporaryDirectory() as td:
                case=generate("workbook_layout",seed)
                path=create_workbook(case,Path(td)/"sales.xlsx")
                self.assertTrue(path.is_file())
                env=Environment(case,workbook_path=path)
                regions=env.call("list_regions",{})
                self.assertEqual(len(regions["regions"]),2)
                wrong=env.call("read_region",{"region":"Archive"})
                env.call("submit_value",{"value":wrong["value"],"source":"Archive"})
                self.assertFalse(env.score()["success"])
                right=env.call("read_region",{"region":"Current"})
                env.call("submit_value",{"value":right["value"],"source":"Current"})
                self.assertTrue(env.score()["success"])

if __name__=="__main__":unittest.main()
