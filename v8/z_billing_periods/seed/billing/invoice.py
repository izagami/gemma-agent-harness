"""Invoices: one per subscription and billing period (format: docs/FORMAT.md)."""
from typing import List, NamedTuple

from billing.dates import fmt
from billing.money import yen
from billing.periods import Period, period_containing
from billing.plans import get_plan
from billing.proration import prorate, segments


class Line(NamedTuple):
    plan: str
    start: object
    end: object
    days: int
    amount: int


class Invoice(NamedTuple):
    customer: str
    name: str
    period: Period
    lines: List[Line]

    @property
    def total(self):
        return sum(l.amount for l in self.lines)


def build_invoice(sub, plans, on):
    """Invoice of `sub` for the billing period that contains date `on`."""
    period = period_containing(sub.start, on)
    lines = []
    for seg in segments(period, sub):
        plan = get_plan(plans, seg.plan)
        lines.append(Line(plan.code, seg.start, seg.end, seg.days, prorate(plan.monthly, seg.days, period.days)))
    return Invoice(sub.customer, sub.name, period, lines)


def render(inv):
    out = [f"INVOICE {inv.customer} {inv.name}",
           f"period {inv.period.label()} ({inv.period.days} days)"]
    for l in inv.lines:
        out.append(f"- {l.plan} {fmt(l.start)}..{fmt(l.end)} {l.days}d {yen(l.amount)}")
    out.append(f"TOTAL {yen(inv.total)} JPY")
    return "\n".join(out)
