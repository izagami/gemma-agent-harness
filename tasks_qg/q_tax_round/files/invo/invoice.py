"""Invoice lines and totals."""
import csv

from .money import to_yen
from .tax import rate_for


def price_line(item, category, unit_price, qty, discount_pct=0):
    """Amounts of one invoice line: (net, tax, total) in whole yen.

    net = amount after the line discount, without tax; tax = consumption tax of the line; total = net + tax.
    """
    gross = unit_price * qty
    rate = rate_for(category)
    keep = 1 - discount_pct / 100
    total = to_yen(gross * (1 + rate) * keep)
    net = to_yen(gross * keep)
    return net, total - net, total


def load_csv(path):
    """Rows of an invoice CSV (columns: item, category, unit_price, qty, discount_pct)."""
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    return [(r["item"], r["category"], int(r["unit_price"]), int(r["qty"]), float(r.get("discount_pct") or 0))
            for r in rows]


def summarize(lines):
    """(rows, subtotal, tax_total, total); rows = [(item, net, tax, total), ...] in input order."""
    rows, sub, tax = [], 0, 0
    for line in lines:
        net, t, total = price_line(*line)
        rows.append((line[0], net, t, total))
        sub += net
        tax += t
    return rows, sub, tax, sub + tax
