import csv
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


@dataclass(slots=True)
class Row:
    order_id: int
    line: int
    ts: str          # "YYYY-MM-DD HH:MM:SS"
    store: str
    sku: str
    qty: int
    unit_price: Decimal
    currency: str
    status: str


def read_rows(path):
    """Returns (rows, rejected_count)."""
    rows, rejected = [], 0
    append = rows.append
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        next(reader, None)
        for r in reader:
            if not r:
                continue
            if len(r) != 9:
                rejected += 1
                continue
            try:
                qty = int(r[5])
                price = Decimal(r[6])
            except (ValueError, InvalidOperation):
                rejected += 1
                continue
            if qty <= 0 or price < 0:
                rejected += 1
                continue
            append(Row(int(r[0]), int(r[1]), r[2], r[3], r[4], qty, price, r[7], r[8]))
    return rows, rejected
