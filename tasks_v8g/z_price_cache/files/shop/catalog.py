"""Product catalog: sku -> (name, category, unit price in yen)."""
import json

from shop.errors import UnknownProduct


class Catalog:
    def __init__(self, bus, products=None):
        self.bus = bus
        self.version = 0
        self._products = {}
        if products:
            self._load(products)

    def _load(self, products):
        self._products = {}
        for p in products:
            if p["price"] < 0:
                raise ValueError(f"negative price for {p['sku']}")
            self._products[p["sku"]] = {"name": p["name"], "category": p.get("category", "regular"),
                                        "price": int(p["price"])}
        self.version += 1

    def reload(self, products):
        """Replace the whole price list (the nightly price file, or a mid-day correction)."""
        self._load(products)
        self.bus.emit("catalog.reloaded", version=self.version)

    def get(self, sku):
        try:
            return self._products[sku]
        except KeyError:
            raise UnknownProduct(sku) from None

    def skus(self):
        return sorted(self._products)

    @classmethod
    def from_file(cls, bus, path):
        with open(path, encoding="utf-8") as f:
            return cls(bus, json.load(f))
