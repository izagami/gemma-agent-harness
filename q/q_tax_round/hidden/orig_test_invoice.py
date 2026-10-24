import os
import unittest

from invo.invoice import load_csv, price_line, summarize
from invo.money import fmt

HERE = os.path.dirname(os.path.abspath(__file__))


class TestLines(unittest.TestCase):
    def test_standard_rate(self):
        self.assertEqual(price_line("pen", "stationery", 150, 3), (450, 45, 495))

    def test_reduced_rate(self):
        self.assertEqual(price_line("tea", "food", 325, 2), (650, 52, 702))

    def test_exempt(self):
        self.assertEqual(price_line("stamp", "exempt", 84, 10), (840, 0, 840))

    def test_round_discount(self):
        self.assertEqual(price_line("pad", "stationery", 1000, 2, 10), (1800, 180, 1980))


class TestTotals(unittest.TestCase):
    def test_summary(self):
        rows, sub, tax, total = summarize([("pen", "stationery", 150, 3, 0), ("tea", "food", 325, 2, 0)])
        self.assertEqual([r[0] for r in rows], ["pen", "tea"])
        self.assertEqual((sub, tax, total), (1100, 97, 1197))

    def test_load(self):
        lines = load_csv(os.path.join(HERE, "..", "data", "invoice_0412.csv"))
        self.assertEqual(len(lines), 7)
        self.assertEqual(lines[0][:4], ("notebook", "stationery", 385, 4))

    def test_fmt(self):
        self.assertEqual(fmt(1234567), "1,234,567")


if __name__ == "__main__":
    unittest.main()
