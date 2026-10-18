import os
import unittest
from types import SimpleNamespace as NS

from report import build_report
from salesrep.clean import dedupe, drop_cancelled

HERE = os.path.dirname(os.path.abspath(__file__))


class ReportTest(unittest.TestCase):
    def test_fixture(self):
        with open(os.path.join(HERE, "data", "fixture_expected.txt"), encoding="utf-8") as f:
            expected = f.read()
        self.assertEqual(build_report(os.path.join(HERE, "data", "fixture.csv")), expected)

    def test_dedupe_keeps_first_position_last_value(self):
        rows = [NS(order_id=1, line=1, v="a"), NS(order_id=2, line=1, v="b"), NS(order_id=1, line=1, v="c")]
        self.assertEqual([r.v for r in dedupe(rows)], ["c", "b"])

    def test_drop_cancelled(self):
        rows = [NS(status="ok"), NS(status="cancel"), NS(status="refund")]
        self.assertEqual([r.status for r in drop_cancelled(rows)], ["ok", "refund"])
