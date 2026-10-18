from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from salesrep.catalog import find_product
from salesrep.rates import rate_for


@dataclass(slots=True)
class Sale:
    order_id: int
    day: str          # YYYY-MM-DD
    month: str        # YYYY-MM
    store: str
    sku: str
    category: str
    qty: int
    amount: Decimal   # JPY, whole yen; negative for refunds


def enrich(rows):
    sales = []
    one = Decimal(1)
    cats = {}
    for r in rows:
        cat = cats.get(r.sku)
        if cat is None:
            product = find_product(r.sku)
            cat = cats[r.sku] = product.category if product else "unknown"
        month = r.ts[:7]
        amount = (r.qty * r.unit_price * rate_for(month, r.currency)).quantize(one, rounding=ROUND_HALF_UP)
        if r.status == "refund":
            amount = -amount
        sales.append(Sale(r.order_id, r.ts[:10], month, r.store, r.sku, cat, r.qty, amount))
    return sales
