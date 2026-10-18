from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from salesrep.catalog import find_product
from salesrep.rates import rate_for


@dataclass
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
    for r in rows:
        product = find_product(r.sku)
        month = r.ts.strftime("%Y-%m")
        amount = (r.qty * r.unit_price * rate_for(month, r.currency)).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        if r.status == "refund":
            amount = -amount
        sales.append(Sale(r.order_id, r.ts.strftime("%Y-%m-%d"), month, r.store, r.sku,
                          product.category if product else "unknown", r.qty, amount))
    return sales
