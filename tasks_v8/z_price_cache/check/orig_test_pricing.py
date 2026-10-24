import json
import os
import unittest

from shop.service import Service

DATA = os.path.join(os.path.dirname(__file__), "..", "data")


def service():
    return Service.from_dir(DATA)


class PricingTest(unittest.TestCase):
    def test_unit_prices(self):
        s = service()
        self.assertEqual(s.pricing.unit_price("C1", "MAT-030"), 1485)
        self.assertEqual(s.pricing.unit_price("C1", "TEA-500"), 4698)
        self.assertEqual(s.pricing.unit_price("C2", "TEA-500"), 5400)

    def test_cache_hits(self):
        s = service()
        s.pricing.unit_price("C3", "TEA-100")
        s.pricing.unit_price("C3", "TEA-100")
        s.pricing.unit_price("C3", "HOJ-200")
        st = s.pricing.stats()
        self.assertEqual((st["hits"], st["misses"]), (1, 2))

    def test_new_tier_used_for_first_lookup(self):
        s = service()
        s.customers.set_tier("C4", "silver")
        self.assertEqual(s.pricing.unit_price("C4", "KYU-001"), 6460)

    def test_reload_before_any_lookup(self):
        s = service()
        with open(os.path.join(DATA, "prices_v2.json"), encoding="utf-8") as f:
            s.catalog.reload(json.load(f))
        self.assertEqual(s.pricing.unit_price("C2", "TEA-100"), 1380)


if __name__ == "__main__":
    unittest.main()
