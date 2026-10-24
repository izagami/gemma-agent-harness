"""Orders.  Prices are fixed when the order is placed."""
from dataclasses import dataclass, field

from shop import rules

# extra percent off a line for large quantities, applied to the line after the unit price
QTY_BREAKS = ((50, 4), (20, 2))


@dataclass
class Line:
    sku: str
    qty: int
    unit: int       # discounted unit price
    total: int


@dataclass
class Order:
    id: int
    day: str
    customer_id: str
    lines: list = field(default_factory=list)

    @property
    def total(self):
        return sum(l.total for l in self.lines)

    @property
    def items(self):
        return sum(l.qty for l in self.lines)


def line_total(unit, qty):
    for min_qty, pct in QTY_BREAKS:
        if qty >= min_qty:
            return rules.apply_percent(unit * qty, pct)
    return unit * qty


class OrderBook:
    def __init__(self, pricing, bus):
        self.pricing = pricing
        self.bus = bus
        self.orders = []

    def place(self, day, cid, items):
        """items: [(sku, qty), ...]"""
        order = Order(len(self.orders) + 1, day, cid)
        for sku, qty in items:
            if qty <= 0:
                raise ValueError(f"quantity must be positive: {sku} x {qty}")
            unit = self.pricing.unit_price(cid, sku)
            order.lines.append(Line(sku, qty, unit, line_total(unit, qty)))
        self.orders.append(order)
        self.bus.emit("order.placed", order=order)
        return order

    def on_day(self, day):
        return [o for o in self.orders if o.day == day]
