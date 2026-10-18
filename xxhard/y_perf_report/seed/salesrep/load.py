import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation


@dataclass
class Row:
    order_id: int
    line: int
    ts: datetime
    store: str
    sku: str
    qty: int
    unit_price: Decimal
    currency: str
    status: str


def parse_row(d):
    """dict from csv.DictReader -> Row, or None if the row is malformed."""
    if None in d or None in d.values():      # too many / too few fields
        return None
    try:
        qty = int(d["qty"])
        price = Decimal(d["unit_price"])
    except (ValueError, InvalidOperation):
        return None
    if qty <= 0 or price < 0:
        return None
    return Row(int(d["order_id"]), int(d["line"]), datetime.strptime(d["ts"], "%Y-%m-%d %H:%M:%S"),
               d["store"], d["sku"], qty, price, d["currency"], d["status"])


def read_rows(path):
    """Returns (rows, rejected_count)."""
    rows, rejected = [], 0
    with open(path, encoding="utf-8", newline="") as f:
        for d in csv.DictReader(f):
            r = parse_row(d)
            if r is None:
                rejected += 1
            else:
                rows.append(r)
    return rows, rejected
