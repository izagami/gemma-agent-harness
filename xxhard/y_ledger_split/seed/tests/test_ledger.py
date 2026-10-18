import unittest
from datetime import date

import ledger
from ledger import Ledger, LedgerError, Money, convert, format_money, parse_money


class MoneyTest(unittest.TestCase):
    def tearDown(self):
        ledger.clear_rates()
        ledger.set_default_currency("JPY")

    def test_parse_format(self):
        self.assertEqual(parse_money("1,234.50 USD"), Money("USD", 123450))
        self.assertEqual(parse_money("-500"), Money("JPY", -500))
        self.assertEqual(format_money(Money("USD", -123456)), "-1,234.56 USD")
        self.assertEqual(str(Money("JPY", 1000000)), "1,000,000 JPY")
        for bad in ["", "1.5 JPY", "12 XXX", "abc"]:
            with self.assertRaises(LedgerError):
                parse_money(bad)

    def test_arithmetic(self):
        self.assertEqual(Money("JPY", 5) + Money("JPY", 7) - Money("JPY", 2), Money("JPY", 10))
        self.assertEqual(-Money("USD", 3) * 2, Money("USD", -6))
        with self.assertRaises(LedgerError):
            Money("JPY", 1) + Money("USD", 1)

    def test_convert(self):
        ledger.set_rate("USD", "JPY", "150.5")
        self.assertEqual(convert(Money("USD", 199), "JPY"), Money("JPY", 299))
        self.assertEqual(convert(Money("JPY", 301), "USD"), Money("USD", 200))
        with self.assertRaises(LedgerError):
            convert(Money("EUR", 1), "JPY")

    def test_default_currency(self):
        ledger.set_default_currency("USD")
        self.assertEqual(parse_money("2.5"), Money("USD", 250))


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.l = Ledger()
        self.l.open("assets:bank", "asset")
        self.l.open("Income:Salary", "income")

    def test_post_and_balance(self):
        self.l.post(date(2026, 1, 2), "pay", [("Assets:Bank", "100"), ("Income:Salary", "-100")])
        self.l.post(date(2026, 1, 1), "pay", [("Assets:Bank", "50"), ("Income:Salary", "-50")])
        self.assertEqual([t.date.day for t in self.l.transactions], [1, 2])
        self.assertEqual(self.l.balance("assets:bank"), Money("JPY", 150))
        self.assertEqual(self.l.balance("Assets", until=date(2026, 1, 2)), Money("JPY", 50))

    def test_unbalanced(self):
        with self.assertRaises(LedgerError):
            self.l.post(date(2026, 1, 1), "x", [("Assets:Bank", "100"), ("Income:Salary", "-90")])
        with self.assertRaises(LedgerError):
            self.l.post(date(2026, 1, 1), "x", [("Assets:Cash", "1"), ("Income:Salary", "-1")])

    def test_csv_roundtrip(self):
        self.l.post(date(2026, 1, 2), "pay, bonus", [("Assets:Bank", "1,000"), ("Income:Salary", "-1,000")])
        text = ledger.dump_csv(self.l)
        again = ledger.load_csv(text)
        self.assertEqual(ledger.dump_csv(again), text)
        with self.assertRaises(LedgerError):
            ledger.load_csv("a,b\n1,2\n")
