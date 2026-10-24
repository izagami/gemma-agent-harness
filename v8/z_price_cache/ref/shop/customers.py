"""Customer registry with loyalty tiers."""
import json
from dataclasses import dataclass

from shop.errors import UnknownCustomer
from shop.rules import TIER_DISCOUNT


@dataclass
class Customer:
    id: str
    name: str
    tier: str = "standard"


class Customers:
    def __init__(self, bus, rows=()):
        self.bus = bus
        self._by_id = {}
        for r in rows:
            self.add(r["id"], r["name"], r.get("tier", "standard"))

    def add(self, cid, name, tier="standard"):
        if tier not in TIER_DISCOUNT:
            raise ValueError(f"unknown tier: {tier}")
        self._by_id[cid] = Customer(cid, name, tier)

    def get(self, cid):
        try:
            return self._by_id[cid]
        except KeyError:
            raise UnknownCustomer(cid) from None

    def tier_of(self, cid):
        return self.get(cid).tier

    def set_tier(self, cid, tier):
        """Upgrade/downgrade a customer.  Listeners are told about the change."""
        if tier not in TIER_DISCOUNT:
            raise ValueError(f"unknown tier: {tier}")
        c = self.get(cid)
        if c.tier == tier:
            return
        old = c.tier
        c.tier = tier          # commit first: listeners read the new state
        self.bus.emit("customer.tier_changed", customer_id=cid, old=old, new=tier)

    def all(self):
        return [self._by_id[k] for k in sorted(self._by_id)]

    @classmethod
    def from_file(cls, bus, path):
        with open(path, encoding="utf-8") as f:
            return cls(bus, json.load(f))
