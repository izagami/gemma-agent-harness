"""Business-day arithmetic (docs/SPEC.md)."""
import datetime as dt

ONE = dt.timedelta(days=1)


def add_business_days(cal, start, n):
    """The date n business days after `start` (before it when n < 0); `start` itself is never counted."""
    hs = cal.holidays(start.year)
    step = ONE if n >= 0 else -ONE
    day, remaining = start, n
    while remaining > 0:
        day += step
        if cal.is_business_day(day, hs):
            remaining -= 1
    return day


def count_business_days(cal, first, last):
    """Number of business days from `first` to `last`, both included."""
    if first > last:
        raise ValueError("first is after last")
    n, day = 0, first
    while day < last:
        if cal.is_business_day(day):
            n += 1
        day += ONE
    return n
