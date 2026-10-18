import statistics
from decimal import Decimal


def by_store_month(sales):
    """{(store, month): total} for every pair that has sales."""
    out = {}
    for s in sales:
        k = (s.store, s.month)
        out[k] = out.get(k, 0) + s.amount
    return {k: Decimal(0) + out[k] for k in sorted(out)}


def by_category(sales):
    """[(category, qty, total)] sorted by total desc, then category."""
    qty, tot = {}, {}
    for s in sales:
        qty[s.category] = qty.get(s.category, 0) + s.qty
        tot[s.category] = tot.get(s.category, 0) + s.amount
    rows = [(c, qty[c], Decimal(0) + tot[c]) for c in sorted(tot)]
    return sorted(rows, key=lambda r: (-r[2], r[0]))


def top_skus(sales, n=10):
    totals = {}
    for s in sales:
        totals[s.sku] = totals.get(s.sku, Decimal(0)) + s.amount
    ranked = sorted(totals.items(), key=lambda kv: kv[0])
    ranked = sorted(ranked, key=lambda kv: kv[1], reverse=True)
    return ranked[:n]


def best_day(sales):
    """(day, total) with the highest total; the earliest day wins a tie."""
    days = {}
    for s in sales:
        days[s.day] = days.get(s.day, Decimal(0)) + s.amount
    best = None
    for day in sorted(days):
        if best is None or days[day] > best[1]:
            best = (day, days[day])
    return best


def order_stats(sales):
    """(order count, median order total, mean order total rounded to whole yen)."""
    orders = {}
    for s in sales:
        orders[s.order_id] = orders.get(s.order_id, Decimal(0)) + s.amount
    values = list(orders.values())
    mean = (sum(values, Decimal(0)) / len(values)).quantize(Decimal(1))
    return len(values), statistics.median(values), mean
