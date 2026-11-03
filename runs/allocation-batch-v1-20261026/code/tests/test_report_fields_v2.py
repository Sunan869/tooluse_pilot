import unittest
from pathlib import Path
from tooluse_pilot.real_w6_reconciliation import report_valid
class ExplicitFieldTests(unittest.TestCase):
    answer=("73800","17","Order08","9100")
    def test_real_gpt_report(self):
        self.assertTrue(report_valid(Path(__file__).with_name("gpt_report_fixture.txt").read_text(),self.answer))
    def test_legacy_formats(self):
        for text in ["total=73800 count=17 winner=Order08 amount=9100", "total 73800, count 17, winner Order08, amount 9100", "Total: 73800; Count: 17; Winner: Order08; Winner amount: 9100."]:
            with self.subTest(text=text):self.assertTrue(report_valid(text,self.answer))
    def test_wrong_missing_and_conflicting(self):
        base="Total: 73800\nCount: 17\nWinner: Order08\nAmount: 9100"
        for text in [base.replace("73800","73801"),base.replace("Count: 17\n",""),base+"\nWinner: Alpha",base+"; amount=10000",base+"\nAmount: 9100.5",base+"\nCount: -17",base+"\nTotal: nonsense",base+"\nWinner amount: 10000"]:
            with self.subTest(text=text):self.assertFalse(report_valid(text,self.answer))
    def test_identical_duplicates(self):
        self.assertTrue(report_valid("total=73800 count=17 winner=Order08 amount=9100; winner=Order08",self.answer))
