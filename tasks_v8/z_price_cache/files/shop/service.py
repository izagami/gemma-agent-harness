"""Wire the parts together and replay scenario files.

A scenario is a JSON-lines file; each line is one operation:
  {"op": "order",  "day": "2026-05-01", "customer": "C1", "items": [["SKU", qty], ...]}
  {"op": "tier",   "customer": "C2", "tier": "gold"}
  {"op": "reload", "file": "prices_v2.json"}            (path relative to the scenario file)
  {"op": "report", "day": "2026-05-01"}                 (prints the daily report)
"""
import json
import os

from shop.catalog import Catalog
from shop.customers import Customers
from shop.events import Bus
from shop.orders import OrderBook
from shop.pricing import Pricing
from shop.report import daily_report


class Service:
    def __init__(self, products, customer_rows):
        self.bus = Bus()
        self.catalog = Catalog(self.bus, products)
        self.customers = Customers(self.bus, customer_rows)
        self.pricing = Pricing(self.catalog, self.customers, self.bus)
        self.book = OrderBook(self.pricing, self.bus)

    @classmethod
    def from_dir(cls, path):
        with open(os.path.join(path, "catalog.json"), encoding="utf-8") as f:
            products = json.load(f)
        with open(os.path.join(path, "customers.json"), encoding="utf-8") as f:
            rows = json.load(f)
        return cls(products, rows)

    def replay(self, scenario_path, out):
        base = os.path.dirname(os.path.abspath(scenario_path))
        with open(scenario_path, encoding="utf-8") as f:
            for n, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                op = json.loads(line)
                kind = op["op"]
                if kind == "order":
                    self.book.place(op["day"], op["customer"], [tuple(x) for x in op["items"]])
                elif kind == "tier":
                    self.customers.set_tier(op["customer"], op["tier"])
                elif kind == "reload":
                    with open(os.path.join(base, op["file"]), encoding="utf-8") as pf:
                        self.catalog.reload(json.load(pf))
                elif kind == "report":
                    out.write(daily_report(self.book, self.customers, op["day"]) + "\n")
                else:
                    raise ValueError(f"{scenario_path}:{n}: unknown op {kind!r}")
