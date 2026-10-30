import unittest
from tooluse_pilot.real_w6_reconciliation import report_valid
class WinnerAmountTests(unittest.TestCase):
 def test_correct_compound_label(self):
  self.assertTrue(report_valid("Total: 23000\nCount: 4\nWinner: Alpha\nWinner amount: 8000",("23000","4","Alpha","8000")))
 def test_contradictory_winner(self):
  self.assertFalse(report_valid("Total: 23000; Count: 4; Winner: Alpha; Winner amount: 8000; Winner: Beta",("23000","4","Alpha","8000")))
 def test_wrong_amount(self):
  self.assertFalse(report_valid("Total: 23000; Count: 4; Winner: Alpha; Winner amount: 9000",("23000","4","Alpha","8000")))
