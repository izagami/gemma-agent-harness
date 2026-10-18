import unittest
from datetime import date

import ledger

CSV = """txn,date,description,account,amount
1,2026-01-05,open,Assets:Bank,"1,000 JPY"
1,2026-01-05,open,Equity:Opening,"-1,000 JPY"
2,2026-02-07,lunch,Expenses:Food,800 JPY
2,2026-02-07,lunch,Assets:Bank,-800 JPY
"""


class ReportTest(unittest.TestCase):
    def setUp(self):
        self.book = ledger.load_csv(CSV)

    def test_trial_balance(self):
        tb = ledger.trial_balance(self.book)
        self.assertEqual(list(tb), ["Assets:Bank", "Equity:Opening", "Expenses:Food"])
        self.assertEqual(tb["Assets:Bank"], ledger.Money("JPY", 200))

    def test_balance_report(self):
        text = ledger.balance_report(self.book, until=date(2026, 2, 1))
        self.assertEqual(text.splitlines()[0], "[asset]")
        self.assertIn("Equity:Opening", text)
        self.assertNotIn("Expenses", text)

    def test_monthly(self):
        lines = ledger.monthly_report(self.book, "expenses", 2026).splitlines()
        self.assertEqual(lines[0], "Expenses 2026 (JPY)")
        self.assertEqual(lines[2].split(), ["2026-02", "800", "JPY"])
        self.assertEqual(len(lines), 13)
