"""Product catalog. SKUs above P2000 are not in the catalog.

A few SKUs were re-listed later under another category; those appear twice in
PRODUCTS and the first entry is the valid one.
"""
import random
from dataclasses import dataclass

CATEGORIES = ["food", "drink", "snack", "kitchen", "stationery", "toys", "garden",
              "tools", "beauty", "health", "pets", "books"]


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    category: str


def _build():
    rnd = random.Random(42)
    products = [Product(f"P{i:04d}", f"item-{i}", rnd.choice(CATEGORIES)) for i in range(1, 2001)]
    for i in rnd.sample(range(1, 2001), 30):
        products.append(Product(f"P{i:04d}", f"item-{i}-relisted", rnd.choice(CATEGORIES)))
    return products


PRODUCTS = _build()


_BY_SKU = {}
for _p in PRODUCTS:
    _BY_SKU.setdefault(_p.sku, _p)


def find_product(sku):
    return _BY_SKU.get(sku)
