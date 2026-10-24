"""Command line.

  python3 -m billing invoice --on YYYY-MM-DD [--data DIR] CUSTOMER [CUSTOMER ...]
  python3 -m billing run --on YYYY-MM-DD [--data DIR]          (every customer, sorted by id)
  python3 -m billing periods --count N [--data DIR] CUSTOMER   (first N periods)

DIR defaults to ./data and must contain plans.csv and subscriptions.csv.
Invoices are separated by one blank line.  Exit status: 0 ok, 1 data error, 2 usage error.
"""
import argparse
import os
import sys

from billing.dates import parse_date
from billing.invoice import build_invoice, render
from billing.periods import periods
from billing.plans import PlanError, load_plans
from billing.subscriptions import SubscriptionError, load_subscriptions


def _date(s):
    try:
        return parse_date(s)
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def parser():
    p = argparse.ArgumentParser(prog="billing")
    sub = p.add_subparsers(dest="cmd", required=True)
    for name in ("invoice", "run"):
        s = sub.add_parser(name)
        s.add_argument("--on", type=_date, required=True)
        s.add_argument("--data", default="data")
        if name == "invoice":
            s.add_argument("customers", nargs="+")
    s = sub.add_parser("periods")
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--data", default="data")
    s.add_argument("customer")
    return p


def load(data):
    return (load_plans(os.path.join(data, "plans.csv")),
            load_subscriptions(os.path.join(data, "subscriptions.csv")))


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        plans, subs = load(args.data)
        if args.cmd == "periods":
            sub = subs[args.customer] if args.customer in subs else None
            if sub is None:
                print(f"error: unknown customer: {args.customer}", file=sys.stderr)
                return 1
            for p, _ in zip(periods(sub.start), range(args.count)):
                print(f"{p.index:3d} {p.label()} {p.days}")
            return 0
        ids = sorted(subs) if args.cmd == "run" else args.customers
        docs = []
        for cid in ids:
            if cid not in subs:
                print(f"error: unknown customer: {cid}", file=sys.stderr)
                return 1
            sub = subs[cid]
            if args.on < sub.start:
                continue
            docs.append(render(build_invoice(sub, plans, args.on)))
        print("\n\n".join(docs))
        return 0
    except (OSError, PlanError, SubscriptionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
