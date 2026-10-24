"""Billing periods.

A subscription is billed in monthly periods anchored on its start date (the "anchor").
Period 0 starts on the anchor; each period ends the day before the next one starts.
"""
from typing import NamedTuple

from billing.dates import ONE_DAY, add_months, day_span, fmt


class Period(NamedTuple):
    index: int
    start: object  # datetime.date
    end: object    # datetime.date, inclusive

    @property
    def days(self):
        return day_span(self.start, self.end)

    def contains(self, d):
        return self.start <= d <= self.end

    def label(self):
        return f"{fmt(self.start)}..{fmt(self.end)}"


def next_start(start):
    """Start of the period following the one that starts on `start`."""
    return add_months(start, 1)


def periods(anchor):
    """Yield the periods of a subscription anchored on `anchor` (endless generator)."""
    start, k = anchor, 0
    while True:
        nxt = next_start(start)
        yield Period(k, start, nxt - ONE_DAY)
        start, k = nxt, k + 1


def period_containing(anchor, d):
    """The billing period that contains date d."""
    if d < anchor:
        raise ValueError(f"{fmt(d)} is before the subscription start {fmt(anchor)}")
    for p in periods(anchor):
        if p.end >= d:
            return p


def nth_period(anchor, n):
    for p in periods(anchor):
        if p.index == n:
            return p
