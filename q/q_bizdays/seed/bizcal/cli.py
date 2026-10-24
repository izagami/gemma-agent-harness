"""usage: python3 -m bizcal add DATE N | python3 -m bizcal count FIRST LAST"""
import datetime as dt
import sys

from .calendar import Calendar
from .ops import add_business_days, count_business_days


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        cmd, a, b = argv
        cal = Calendar()
        if cmd == "add":
            print(add_business_days(cal, dt.date.fromisoformat(a), int(b)).isoformat())
        elif cmd == "count":
            print(count_business_days(cal, dt.date.fromisoformat(a), dt.date.fromisoformat(b)))
        else:
            raise ValueError(f"unknown command: {cmd}")
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0
