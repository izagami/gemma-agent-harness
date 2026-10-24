import unittest

from durfmt import format_duration, parse_duration


class ParseTest(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(parse_duration("1h30m"), 5400)
        self.assertEqual(parse_duration("90s"), 90)
        self.assertEqual(parse_duration("2d4h"), 187200)

    def test_fraction(self):
        self.assertEqual(parse_duration("1.5h"), 5400)

    def test_spaces_between_groups(self):
        self.assertEqual(parse_duration(" 1h 30m "), 5400)

    def test_errors(self):
        with self.assertRaisesRegex(ValueError, "^empty duration$"):
            parse_duration("  ")
        with self.assertRaisesRegex(ValueError, "^invalid duration: 'abc'$"):
            parse_duration("abc")


class FormatTest(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_duration(5430), "1h30m30s")
        self.assertEqual(format_duration(90061), "1d1h1m1s")
        self.assertEqual(format_duration(90), "1m30s")

    def test_negative(self):
        with self.assertRaisesRegex(ValueError, "negative duration"):
            format_duration(-1)


if __name__ == "__main__":
    unittest.main()
