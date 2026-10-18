import statistics
from decimal import Decimal


def by_store_month(sales):
    """{(store, month): total} for every pair that has sales."""
    keys = sorted({(s.store, s.month) for s in sales})
    out = {}
    for store, month in keys:
        out[(store, month)] = sum((s.amount for s in sales if s.store == store and s.month == month), Decimal(0))
    return out


def by_category(sales):
    """[(category, qty, total)] sorted by total desc, then category."""
    cats = sorted({s.category for s in sales})
    rows = []
    for c in cats:
        mine = [s for s in sales if s.category == c]
        rows.append((c, sum(s.qty for s in mine), sum((s.amount for s in mine), Decimal(0))))
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
