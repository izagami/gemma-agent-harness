import unittest

from salesrep.fmt import table, yen


class FmtTest(unittest.TestCase):
    def test_yen(self):
        self.assertEqual(yen(0), "0")
        self.assertEqual(yen(1234567), "1,234,567")
        self.assertEqual(yen(-980), "-980")

    def test_table(self):
        t = table(["region", "net"], [["kanto", "1,000"]], width=8)
        self.assertEqual(t.splitlines(), ["region         net", "kanto        1,000"])
