"""Calendar helpers.

Billing works on calendar dates only (no times, no time zones).  All ranges in this
package are *inclusive* on both ends unless a name says otherwise.
"""
import calendar
from datetime import date, timedelta

ONE_DAY = timedelta(days=1)


def parse_date(s):
    """'YYYY-MM-DD' -> date (ValueError with a readable message otherwise)."""
    try:
        return date.fromisoformat(s.strip())
    except (ValueError, AttributeError):
        raise ValueError(f"invalid date: {s!r}") from None


def fmt(d):
    return d.isoformat()


def days_in_month(year, month):
    return calendar.monthrange(year, month)[1]


def add_months(d, n):
    """d shifted by n calendar months.

    When the target month is shorter than d.day the result is clamped to the last day
    of that month: add_months(2026-01-31, 1) == 2026-02-28.
    """
    m0 = d.month - 1 + n
    year, month = d.year + m0 // 12, m0 % 12 + 1
    return date(year, month, min(d.day, days_in_month(year, month)))


def day_span(start, end):
    """Number of days in the inclusive range start..end (start == end -> 1)."""
    if end < start:
        raise ValueError(f"empty range {start}..{end}")
    return (end - start).days + 1


def month_of(d):
    return f"{d.year:04d}-{d.month:02d}"
