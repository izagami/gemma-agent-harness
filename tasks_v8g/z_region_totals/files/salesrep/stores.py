"""Store master data and store id aliases.

data/stores.csv lists the current stores.  When a store is renumbered, the old id is kept in
data/store_aliases.csv (old_id,new_id,since) because some POS terminals keep sending the old id.
"""
import csv
import os
from dataclasses import dataclass


@dataclass
class Store:
    store_id: str
    name: str
    region: str
    pos: str
    opened: str


class StoreDirectory:
    def __init__(self, stores, aliases):
        self.stores = {s.store_id: s for s in stores}
        self.aliases = dict(aliases)

    @classmethod
    def load(cls, data_dir, cfg):
        with open(os.path.join(data_dir, cfg.stores_file), encoding="utf-8", newline="") as f:
            stores = [Store(r["store_id"], r["name"], r["region"], r["pos"], r["opened"]) for r in csv.DictReader(f)]
        aliases = []
        p = os.path.join(data_dir, cfg.aliases_file)
        if os.path.exists(p):
            with open(p, encoding="utf-8", newline="") as f:
                aliases = [(r["old_id"], r["new_id"]) for r in csv.DictReader(f)]
        return cls(stores, aliases)

    def canonical(self, store_id):
        """Follow the alias chain to the current id (unknown ids are returned unchanged)."""
        seen = set()
        while store_id in self.aliases and store_id not in seen:
            seen.add(store_id)
            store_id = self.aliases[store_id]
        return store_id

    def name(self, store_id):
        s = self.stores.get(self.canonical(store_id))
        return s.name if s else "?"
