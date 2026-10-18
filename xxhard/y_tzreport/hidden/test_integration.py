import os
import unittest
from datetime import date

from events import cache
from events.parse import parse_file
from events.report import daily_report, weekly_report
from events.store import EventStore
from events.tz import parse_zone

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
UTC, NYC, JST = parse_zone("UTC"), parse_zone("-05:00"), parse_zone("+09:00")


def load(*names):
    s = EventStore()
    for n in names:
        s.extend(parse_file(os.path.join(DATA, n)))
    return s


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        cache.clear()
        self.store = load("tokyo.log", "nyc.log")

    def test_daily_utc(self):
        self.assertEqual(daily_report(self.store, date(2026, 3, 3), UTC),
                         "# 2026-03-03 (+00:00)\nsearch        5\nlogin         2\nupload        2\n"
                         "TOTAL         9\nusers: aoi, kai, mia, ren\n")

    def test_daily_nyc(self):
        self.assertEqual(daily_report(self.store, date(2026, 3, 2), NYC),
                         "# 2026-03-02 (-05:00)\nsearch        9\nlogin         3\nupload        3\n"
                         "TOTAL        15\nusers: aoi, kai, mia, ren, yui\n")

    def test_daily_twice_then_weekly(self):
        expected = ("# 2026-03-02 (+09:00)\nlogin         4\nsearch        3\nupload        2\n"
                    "TOTAL         9\nusers: aoi, kai, mia, yui\n")
        self.assertEqual(daily_report(self.store, date(2026, 3, 2), JST), expected)
        self.assertEqual(daily_report(self.store, date(2026, 3, 2), JST), expected)
        self.assertEqual(weekly_report(self.store, date(2026, 3, 4), JST),
                         "# week 2026-03-02..2026-03-08 (+09:00)\nsearch       16\nlogin         8\nupload        7\n"
                         "TOTAL        31\nusers: aoi, kai, mia, ren, yui\n")

    def test_late_events(self):
        daily_report(self.store, date(2026, 3, 3), UTC)
        weekly_report(self.store, date(2026, 3, 4), UTC)
        self.store.extend(parse_file(os.path.join(DATA, "late.log")))
        self.assertEqual(daily_report(self.store, date(2026, 3, 3), UTC),
                         "# 2026-03-03 (+00:00)\nsearch        5\nupload        3\nlogin         2\n"
                         "TOTAL        10\nusers: aoi, kai, leo, mia, ren\n")
        self.assertEqual(weekly_report(self.store, date(2026, 3, 4), UTC),
                         "# week 2026-03-02..2026-03-08 (+00:00)\nsearch       15\nlogin         9\nupload        8\n"
                         "TOTAL        32\nusers: aoi, kai, leo, mia, ren, yui\n")
