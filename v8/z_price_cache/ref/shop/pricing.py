"""Customer-specific unit prices.

Looking up a price needs the catalog, the customer's tier and the discount rules; the order desk
asks for the same (customer, sku) pairs all day, so results are memoised.  The cache is kept
correct by listening to the events that change its inputs (see events.py).
"""
from shop import rules


class Pricing:
    # how many SKUs to pre-compute again for a customer whose entries were dropped
    REWARM_LIMIT = 50

    def __init__(self, catalog, customers, bus):
        self.catalog = catalog
        self.customers = customers
        self._cache = {}
        self._hits = 0
        self._misses = 0
        bus.subscribe("customer.tier_changed", self._on_tier_changed)
        bus.subscribe("catalog.reloaded", self._on_reload)

    # -- lookups -------------------------------------------------------------
    def unit_price(self, cid, sku):
        """Discounted unit price in yen for customer cid."""
        key = (cid, sku)
        if key in self._cache:
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        price = self._compute(cid, sku)
        self._cache[key] = price
        return price

    def _compute(self, cid, sku):
        p = self.catalog.get(sku)
        pct = rules.discount_percent(self.customers.tier_of(cid), p["category"])
        return rules.apply_percent(p["price"], pct)

    def stats(self):
        return {"hits": self._hits, "misses": self._misses, "size": len(self._cache)}

    # -- invalidation ----------------------------------------------------------
    def _on_tier_changed(self, customer_id, **_):
        # drop this customer's entries and warm them up again right away, so the
        # next order of a big customer does not pay for the misses
        keys = [k for k in self._cache if k[0] == customer_id]
        for k in keys:
            del self._cache[k]
        for k in keys[: self.REWARM_LIMIT]:
            self._cache[k] = self._compute(*k)

    def _on_reload(self, **_):
        self._cache.clear()
