import unittest

from shop import rules
from shop.orders import line_total


class RulesTest(unittest.TestCase):
    def test_discount(self):
        self.assertEqual(rules.discount_percent("standard", "regular"), 0)
        self.assertEqual(rules.discount_percent("gold", "regular"), 10)
        self.assertEqual(rules.discount_percent("platinum", "sale"), 7)
        self.assertEqual(rules.discount_percent("gold", "bulk"), 13)
        self.assertEqual(rules.discount_percent("silver", "bulk"), 5)

    def test_rounding(self):
        self.assertEqual(rules.apply_percent(1650, 10), 1485)
        self.assertEqual(rules.apply_percent(1005, 10), 905)   # 904.5 -> 905
        self.assertEqual(rules.apply_percent(999, 0), 999)

    def test_quantity_breaks(self):
        self.assertEqual(line_total(100, 19), 1900)
        self.assertEqual(line_total(100, 20), 1960)
        self.assertEqual(line_total(100, 50), 4800)


if __name__ == "__main__":
    unittest.main()
