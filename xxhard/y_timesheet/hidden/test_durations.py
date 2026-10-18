import unittest

from ts.durations import format_minutes, parse_duration
from ts.errors import UsageError


class DurationTest(unittest.TestCase):
    def test_parse(self):
        for text, minutes in [("1h30m", 90), ("90m", 90), ("2h", 120), ("1:05", 65), ("1.5h", 90), ("0.25h", 15)]:
            self.assertEqual(parse_duration(text), minutes, text)

    def test_invalid(self):
        for text in ["", "0m", "1.01h", "abc", "1:60", "h"]:
            with self.assertRaises(UsageError):
                parse_duration(text)

    def test_format(self):
        self.assertEqual([format_minutes(m) for m in (0, 5, 125, 600)], ["0:00", "0:05", "2:05", "10:00"])
