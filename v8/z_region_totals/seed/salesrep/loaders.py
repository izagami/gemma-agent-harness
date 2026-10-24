"""Read sales and refunds exported by the POS systems.

Layout (relative to the data directory):
  sales/<pos>/<YYYY-MM>.csv    date,store,sku,qty,unit_price     one file per POS vendor and month
  refunds/<pos>/<YYYY-MM>.csv  date,store,amount,reason          the file is named after the month it was
                               exported in; a refund belongs to the month of its `date`, so every
                               refunds file of the vendor is scanned.
"""
import csv
import os
from dataclasses import dataclass


@dataclass
class Sale:
    date: str
    store: str
    sku: str
    qty: int
    unit_price: int

    @property
    def amount(self):
        return self.qty * self.unit_price


@dataclass
class Refund:
    date: str
    store: str
    amount: int
    reason: str


def _vendors(base):
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base) if os.path.isdir(os.path.join(base, d)))


def _rows(path):
    with open(path, encoding="utf-8", newline="") as f:
        yield from csv.DictReader(f)


def load_sales(data_dir, cfg, month, directory):
    base = os.path.join(data_dir, cfg.sales_dir)
    out = []
    for pos in _vendors(base):
        path = os.path.join(base, pos, f"{month}.csv")
        if not os.path.exists(path):
            continue
        for r in _rows(path):
            out.append(Sale(r["date"], directory.canonical(r["store"].strip()), r["sku"],
                            int(r["qty"]), int(r["unit_price"])))
    return out


def load_refunds(data_dir, cfg, month):
    base = os.path.join(data_dir, cfg.refunds_dir)
    out = []
    for pos in _vendors(base):
        for fn in sorted(os.listdir(os.path.join(base, pos))):
            if not fn.endswith(".csv"):
                continue
            for r in _rows(os.path.join(base, pos, fn)):
                if r["date"].startswith(month):
                    out.append(Refund(r["date"], r["store"].strip(), int(r["amount"]), r.get("reason", "")))
    return out
