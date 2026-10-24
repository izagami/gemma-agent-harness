"""Command line.

  python3 -m exp [--db PATH] add DATE AMOUNT CATEGORY [--currency CUR] [--note TEXT]
  python3 -m exp [--db PATH] list [--month YYYY-MM] [--category NAME]
  python3 -m exp [--db PATH] import FILE.csv
  python3 -m exp [--db PATH] report --month YYYY-MM [--by category|day] [--format text|csv|json] [--rates PATH]

The store is --db, else $EXP_DB, else ./expenses.json (relative paths are relative to
the current directory).  Errors go to stderr as "error: <message>"; exit status 1 for
data errors, 2 for usage errors.
"""
import argparse
import calendar
import os
import sys

from exp.fmt import expense_line
from exp.importer import ImportError_, import_csv
from exp.models import ValidationError, make_expense
from exp import report
from exp.store import Store, StoreError


def db_path(args):
    return args.db or os.environ.get("EXP_DB") or "expenses.json"


def month_range(month):
    y, m = int(month[:4]), int(month[5:7])
    return f"{month}-01", f"{month}-{calendar.monthrange(y, m)[1]:02d}"


def build_parser():
    p = argparse.ArgumentParser(prog="exp")
    p.add_argument("--db")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("date")
    a.add_argument("amount")
    a.add_argument("category")
    a.add_argument("--currency", default="JPY")
    a.add_argument("--note", default="")
    l = sub.add_parser("list")
    l.add_argument("--month")
    l.add_argument("--category")
    i = sub.add_parser("import")
    i.add_argument("file")
    r = sub.add_parser("report")
    r.add_argument("--month", required=True)
    r.add_argument("--by", choices=["category", "day"], default="category")
    r.add_argument("--format", choices=["text", "csv", "json"], default="text")
    r.add_argument("--rates", default=report.DEFAULT_RATES)
    return p


def cmd_add(store, args):
    e = store.add(lambda i: make_expense(i, args.date, args.amount, args.currency, args.category, args.note))
    store.save()
    print(f"added #{e.id}")


def cmd_list(store, args):
    items = store.expenses
    if args.month:
        items = store.in_range(*month_range(args.month))
    if args.category:
        items = [e for e in items if e.category == args.category.strip().lower()]
    for e in sorted(items, key=lambda e: (e.date, e.id)):
        print(expense_line(e))


def cmd_import(store, args):
    n, skipped = import_csv(store, args.file)
    store.save()
    print(f"imported {n}, skipped {skipped}" if skipped else f"imported {n}")


def cmd_report(store, args):
    rates = report.load_rates(args.rates)
    groups = report.build(store.in_range(*month_range(args.month)), rates, args.by)
    sys.stdout.write(report.render(args.month, args.by, args.format, groups))


COMMANDS = {"add": cmd_add, "list": cmd_list, "import": cmd_import, "report": cmd_report}


def main(argv=None):
    args = build_parser().parse_args(argv)
    if args.cmd == "report" and not report.MONTH.match(args.month):
        print(f"error: invalid month: {args.month}", file=sys.stderr)
        return 2
    try:
        store = Store(db_path(args))
        COMMANDS[args.cmd](store, args)
        return 0
    except (ValidationError, ImportError_, StoreError, report.ReportError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
