import os
import unittest

from shop.report import daily_report
from shop.service import Service

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


class ReportTest(unittest.TestCase):
    def test_format(self):
        s = Service.from_dir(DATA)
        s.book.place("2026-05-02", "C4", [("KYU-001", 1), ("TEA-100", 2)])
        s.book.place("2026-05-02", "C1", [("TEA-100", 20)])
        s.book.place("2026-05-03", "C1", [("TEA-100", 1)])
        self.assertEqual(daily_report(s.book, s.customers, "2026-05-02"),
                         "# 2026-05-02\n"
                         "C1  丸山茶舗          orders=1  items=20  total=22,579\n"
                         "C4  Cafe Lumen    orders=1  items=3  total=9,360\n"
                         "TOTAL  orders=2  items=23  total=31,939")

    def test_empty_day(self):
        s = Service.from_dir(DATA)
        self.assertEqual(daily_report(s.book, s.customers, "2026-05-09"),
                         "# 2026-05-09\nTOTAL  orders=0  items=0  total=0")


if __name__ == "__main__":
    unittest.main()
