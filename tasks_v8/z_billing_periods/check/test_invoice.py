import os
import unittest
from datetime import date

from billing.cli import load
from billing.invoice import build_invoice, render
from billing.periods import period_containing

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


class InvoiceTest(unittest.TestCase):
    def setUp(self):
        self.plans, self.subs = load(DATA)

    def test_simple_period(self):
        p = period_containing(date(2026, 1, 10), date(2026, 3, 15))
        self.assertEqual((p.start, p.end, p.days), (date(2026, 3, 10), date(2026, 4, 9), 31))

    def test_first_period_of_month_end_anchor(self):
        p = period_containing(date(2026, 1, 31), date(2026, 2, 10))
        self.assertEqual((p.start, p.end), (date(2026, 1, 31), date(2026, 2, 27)))

    def test_render_full_period(self):
        inv = build_invoice(self.subs["C001"], self.plans, date(2026, 3, 15))
        self.assertEqual(render(inv), "INVOICE C001 Tanaka Aoi\n"
                                      "period 2026-03-10..2026-04-09 (31 days)\n"
                                      "- standard 2026-03-10..2026-04-09 31d 1,980\n"
                                      "TOTAL 1,980 JPY")

    def test_after_change_whole_period_new_plan(self):
        inv = build_invoice(self.subs["C002"], self.plans, date(2026, 3, 20))
        self.assertEqual([(l.plan, l.amount) for l in inv.lines], [("pro", 4980)])
