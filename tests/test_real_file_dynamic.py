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
    def test_final_stage_requires_updated_report_and_cells(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(0,p);env=Environment(case,p)
            from tooluse_pilot.real_file_dynamic import expected
            first=expected(env.workbook,160000,["Beijing"])
            for cell,value in zip(("B4","B5","B6"),first):
                env.call("write_cell",{"sheet": "Decision","cell":cell,"value":value})
            env.call("save_workbook",{})
            env.call("write_report",{"text":f"{first[0]} {first[1]}"})
            env.call("receive_update",{})
            env.call("finish",{})
            self.assertFalse(env.score()["success"])
            self.assertFalse(env.score()["checks"]["result"])
            env.close()

    def test_reference_preserves_new_constraints(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(4,p)
            score=reference(case,p)
            self.assertTrue(score["checks"]["requirements"])
            self.assertTrue(score["checks"]["report"])

    def test_grouped_report_amount_accepted(self):
        from tooluse_pilot.real_file_dynamic import expected
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(0,p);e=Environment(case,p)
            vendor,amount,count=expected(e.workbook,160000,["Beijing"])
            for cell,val in zip(("B4","B5","B6"),(vendor,amount,count)):
                e.call("write_cell",{"sheet":"Decision","cell":cell,"value":val})
            e.call("save_workbook",{})
            e.call("write_report",{"text":f"Recommended {vendor}, price {int(amount):,} CNY"})
            update=e.call("receive_update",{})
            self.assertTrue(e.initial_ok)
            self.assertEqual(update["budget"],130000)
            e.close()

    def test_invalid_report_amount_rejected(self):
        from tooluse_pilot.real_file_dynamic import expected
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(0,p);e=Environment(case,p)
            vendor,amount,count=expected(e.workbook,160000,["Beijing"])
            for cell,val in zip(("B4","B5","B6"),(vendor,amount,count)):
                e.call("write_cell",{"sheet":"Decision","cell":cell,"value":val})
            e.call("save_workbook",{})
            e.call("write_report",{"text":f"Recommended {vendor}, price {int(amount)+1:,} CNY"})
            with self.assertRaises(ValueError):e.call("receive_update",{})
            e.close()

    def test_skip_initial_files_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"source";case=generate(1,p);e=Environment(case,p)
            with self.assertRaises(ValueError):e.call("receive_update",{})
            e.close()
