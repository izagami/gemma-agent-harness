import unittest

from salesrep.stores import Store, StoreDirectory


class StoresTest(unittest.TestCase):
    def test_canonical(self):
        d = StoreDirectory([Store("B", "b", "r", "p", "2020-01-01")], [("A", "B"), ("Z", "A")])
        self.assertEqual(d.canonical("Z"), "B")
        self.assertEqual(d.canonical("B"), "B")
        self.assertEqual(d.canonical("Q"), "Q")
        self.assertEqual(d.name("A"), "b")
