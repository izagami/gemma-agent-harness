import datetime as dt
import unittest

from bizcal.calendar import Calendar, load_holidays
from bizcal.ops import add_business_days, count_business_days

D = dt.date.fromisoformat


class OpsTest(unittest.TestCase):
    def setUp(self):
        self.cal = Calendar()

    def test_holidays_file(self):
        h = load_holidays()
        self.assertEqual(h[D("2026-05-03")], "憲法記念日")
        self.assertNotIn(D("2026-05-07"), h)

    def test_add_in_a_normal_week(self):
        self.assertEqual(add_business_days(self.cal, D("2026-06-01"), 4), D("2026-06-05"))

    def test_add_skips_weekend_and_holidays(self):
        self.assertEqual(add_business_days(self.cal, D("2026-04-28"), 3), D("2026-05-07"))

    def test_count_week(self):
        self.assertEqual(count_business_days(self.cal, D("2026-06-01"), D("2026-06-07")), 5)

    def test_count_rejects_reversed_range(self):
        with self.assertRaisesRegex(ValueError, "first is after last"):
            count_business_days(self.cal, D("2026-06-02"), D("2026-06-01"))

    def test_weekend_holiday(self):
        self.assertFalse(self.cal.is_business_day(D("2026-05-03")))
        self.assertTrue(self.cal.is_business_day(D("2026-05-07")))


if __name__ == "__main__":
    unittest.main()
