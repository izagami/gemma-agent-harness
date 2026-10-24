import unittest

from ttlcache import FakeClock, TTLCache


class CacheTest(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.c = TTLCache(3, 10, clock=self.clock)

    def test_set_get(self):
        self.c.set("a", 1)
        self.assertEqual(self.c.get("a"), 1)
        self.assertIsNone(self.c.get("b"))
        self.assertEqual(self.c.get("b", 7), 7)

    def test_lru_eviction(self):
        for k in "abc":
            self.c.set(k, k)
        self.c.get("a")
        self.c.set("d", "d")
        self.assertNotIn("b", self.c)
        self.assertIn("a", self.c)
        self.assertEqual(self.c.stats()["evictions"], 1)

    def test_expiry(self):
        self.c.set("a", 1)
        self.clock.advance(25)
        self.assertIsNone(self.c.get("a"))
        self.assertEqual(self.c.stats()["expirations"], 1)

    def test_bad_ttl(self):
        with self.assertRaises(ValueError):
            self.c.set("a", 1, ttl=0)

    def test_delete(self):
        self.c.set("a", 1)
        self.assertTrue(self.c.delete("a"))
        self.assertFalse(self.c.delete("a"))


if __name__ == "__main__":
    unittest.main()
