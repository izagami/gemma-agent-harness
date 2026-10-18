"""python3 -m events {daily|weekly} YYYY-MM-DD [--zone +09:00] LOGFILE..."""
import argparse
import sys
from datetime import date

from events.parse import ParseError, parse_file
from events.report import daily_report, weekly_report
from events.store import EventStore
from events.tz import parse_zone


def main(argv=None):
    p = argparse.ArgumentParser(prog="python3 -m events")
    p.add_argument("period", choices=["daily", "weekly"])
    p.add_argument("day", type=date.fromisoformat)
    p.add_argument("files", nargs="+")
    p.add_argument("--zone", default="UTC", type=parse_zone)
    a = p.parse_args(argv)
    store = EventStore()
    try:
        for path in a.files:
            store.extend(parse_file(path))
    except ParseError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    fn = daily_report if a.period == "daily" else weekly_report
    sys.stdout.write(fn(store, a.day, a.zone))
    return 0


if __name__ == "__main__":
    sys.exit(main())
