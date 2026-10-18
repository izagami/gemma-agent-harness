import unittest
from datetime import date, datetime, timedelta, timezone

from events import cache
from events.aggregate import daily_counts
from events.parse import ParseError, parse_line, parse_text
from events.store import EventStore
from events.tz import day_bounds, parse_zone, week_days, zone_name

JST = timezone(timedelta(hours=9))


class ParseTest(unittest.TestCase):
    def test_line(self):
        ev = parse_line("2026-03-02T08:10:00+09:00, LOGIN ,aoi,3")
        self.assertEqual((ev.kind, ev.user, ev.count), ("login", "aoi", 3))
        self.assertEqual(ev.ts, datetime(2026, 3, 1, 23, 10, tzinfo=timezone.utc))

    def test_errors(self):
        for bad in ["2026-03-02T08:10:00,login,aoi", "x,login,aoi", "2026-03-02T08:10:00Z,login", "2026-03-02T08:10:00Z,a,b,0"]:
            with self.assertRaises(ParseError):
                parse_line(bad)

    def test_text_skips_comments(self):
        self.assertEqual(len(parse_text("# c\n\n2026-03-02T08:10:00Z,a,b\n")), 1)


class TzTest(unittest.TestCase):
    def test_parse_zone(self):
        self.assertEqual(parse_zone("+09:00"), JST)
        self.assertEqual(parse_zone("UTC-0530").utcoffset(None), -timedelta(hours=5, minutes=30))
        self.assertEqual(zone_name(parse_zone("utc")), "+00:00")
        self.assertEqual(zone_name(parse_zone("-05:00")), "-05:00")
        with self.assertRaises(ValueError):
            parse_zone("+15:00")

    def test_day_bounds(self):
        start, end = day_bounds(date(2026, 3, 2), JST)
        self.assertEqual(start, datetime(2026, 3, 1, 15, tzinfo=timezone.utc))
        self.assertEqual(end - start, timedelta(days=1))

    def test_week(self):
        self.assertEqual(week_days(date(2026, 3, 4))[0], date(2026, 3, 2))
        self.assertEqual(week_days(date(2026, 3, 8))[-1], date(2026, 3, 8))


class StoreTest(unittest.TestCase):
    def test_between_same_zone(self):
        evs = parse_text("2026-03-02T23:00:00+09:00,a,u\n2026-03-03T01:00:00+09:00,b,u\n2026-03-03T09:00:00+09:00,c,u\n")
        s = EventStore(evs)
        start, end = day_bounds(date(2026, 3, 3), JST)
        self.assertEqual([e.kind for e in s.between(start, end)], ["b", "c"])
        self.assertEqual(len(s), 3)


class CacheTest(unittest.TestCase):
    def test_hits(self):
        cache.clear()
        s = EventStore(parse_text("2026-03-02T10:00:00+09:00,login,u,2\n"))
        self.assertEqual(daily_counts(s, date(2026, 3, 2), JST), {"login": 2})
        self.assertEqual(daily_counts(s, date(2026, 3, 2), JST), {"login": 2})
        self.assertEqual(cache.stats(), {"hits": 1, "misses": 1})
