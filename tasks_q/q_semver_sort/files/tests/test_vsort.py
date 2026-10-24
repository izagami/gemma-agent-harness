import unittest

from vsort.compare import compare, sort_versions
from vsort.parse import InvalidVersion, parse


class TestParse(unittest.TestCase):
    def test_full(self):
        v = parse("v1.2.3-rc.1+build.5")
        self.assertEqual((v.major, v.minor, v.patch, v.pre, v.build), (1, 2, 3, ("rc", "1"), ("build", "5")))

    def test_invalid(self):
        for s in ["1.2", "1.2.x", "1.2.3-", "a.b.c"]:
            with self.assertRaises(InvalidVersion):
                parse(s)


class TestCompare(unittest.TestCase):
    def test_core(self):
        self.assertEqual(compare("1.3.10", "1.4.0"), -1)
        self.assertEqual(compare("2.0.0", "1.9.9"), 1)

    def test_prerelease_lower(self):
        self.assertEqual(compare("1.0.0-rc.1", "1.0.0"), -1)
        self.assertEqual(compare("1.0.0-alpha", "1.0.0-beta"), -1)

    def test_sort(self):
        vs = [parse(s) for s in ["1.0.0", "1.0.0-beta", "0.9.0"]]
        self.assertEqual([v.text for v in sort_versions(vs)], ["0.9.0", "1.0.0-beta", "1.0.0"])


if __name__ == "__main__":
    unittest.main()
