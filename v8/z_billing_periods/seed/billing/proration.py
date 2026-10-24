"""Splitting a period at a plan change and prorating the charges."""
from decimal import ROUND_HALF_UP, Decimal
from typing import NamedTuple

from billing.dates import ONE_DAY


class Segment(NamedTuple):
    plan: str
    start: object
    end: object  # inclusive
    days: int


def segments(period, sub):
    """Split `period` into the parts billed on each plan (1 or 2 segments, in date order).

    The old plan is billed up to the day before change_on, the new plan from change_on on.
    """
    c = sub.change_on
    if c is None or c > period.end:
        return [Segment(sub.plan, period.start, period.end, period.days)]
    if c <= period.start:
        return [Segment(sub.change_to, period.start, period.end, period.days)]
    old = Segment(sub.plan, period.start, c - ONE_DAY, (c - period.start).days)
    new = Segment(sub.change_to, c, period.end, (period.end - c).days)
    return [old, new]


def prorate(monthly, days, period_days):
    """monthly * days / period_days, rounded to whole yen (half up)."""
    if days == period_days:
        return monthly
    amount = Decimal(monthly) * days / period_days
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))
