import unittest
from datetime import date

from billing.dates import add_months, day_span, parse_date


class DatesTest(unittest.TestCase):
    def test_add_months_plain(self):
        self.assertEqual(add_months(date(2026, 1, 10), 1), date(2026, 2, 10))
        self.assertEqual(add_months(date(2026, 11, 5), 3), date(2027, 2, 5))

    def test_add_months_clamps(self):
        self.assertEqual(add_months(date(2026, 1, 31), 1), date(2026, 2, 28))
        self.assertEqual(add_months(date(2028, 1, 31), 1), date(2028, 2, 29))
        self.assertEqual(add_months(date(2026, 3, 31), 1), date(2026, 4, 30))

    def test_day_span(self):
        self.assertEqual(day_span(date(2026, 3, 10), date(2026, 4, 9)), 31)
        self.assertEqual(day_span(date(2026, 3, 10), date(2026, 3, 10)), 1)

    def test_parse(self):
        self.assertEqual(parse_date(" 2026-02-03 "), date(2026, 2, 3))
        with self.assertRaises(ValueError):
            parse_date("2026-02-30")
