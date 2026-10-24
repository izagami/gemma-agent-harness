import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import report

DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "shop.db")


class TestReport(unittest.TestCase):
    def test_columns(self):
        cols, rows = report.run(DB, "customers_without_orders")
        self.assertEqual(cols, ["id", "name"])

    def test_running_total_days(self):
        cols, rows = report.run(DB, "running_total")
        self.assertEqual(cols, ["day", "revenue", "running_total"])
        self.assertEqual(rows[0][0], "2026-01-05")


if __name__ == "__main__":
    unittest.main()
