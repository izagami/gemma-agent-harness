"""Sum sales and refunds per store and per region."""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class Totals:
    sales: int = 0
    refunds: int = 0

    @property
    def net(self):
        return self.sales - self.refunds

    def add(self, other):
        self.sales += other.sales
        self.refunds += other.refunds


def store_totals(sales, refunds):
    by_store = defaultdict(Totals)
    for s in sales:
        by_store[s.store].sales += s.amount
    for r in refunds:
        by_store[r.store].refunds += r.amount
    return by_store


def region_totals(cfg, directory, sales, refunds):
    """{region name: Totals} for every configured region, plus per-store rows for --detail."""
    by_store = store_totals(sales, refunds)
    regions, detail = {}, {}
    for name in sorted(cfg.regions):
        region = cfg.regions[name]
        tot = Totals()
        rows = []
        seen = set()
        for sid in region.stores:
            key = directory.canonical(sid)
            if key in seen:  # an old id listed next to its new id: count the store once
                continue
            seen.add(key)
            st = by_store.get(key, Totals())
            tot.add(st)
            rows.append((sid, st))
        regions[name] = tot
        detail[name] = rows
    return regions, detail


def unassigned(cfg, directory, sales, refunds):
    """Store ids that have data but are not listed in any region (reported as a warning)."""
    known = {directory.canonical(s) for r in cfg.regions.values() for s in r.stores}
    seen = {s.store for s in sales} | {directory.canonical(r.store) for r in refunds}
    return sorted(seen - known)
