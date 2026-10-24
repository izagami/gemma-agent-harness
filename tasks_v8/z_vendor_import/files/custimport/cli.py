"""Command line interface.

  python3 -m custimport import STORE FILE [FILE ...]
  python3 -m custimport list STORE [--source VENDOR]
"""
import argparse
import sys

from custimport import reader
from custimport.store import Store


def cmd_import(args):
    store = Store(args.store)
    for path in args.files:
        try:
            records, enc = reader.read_file(path)
        except (OSError, reader.ReadError) as e:
            print(f"error: {path}: {e}", file=sys.stderr)
            return 1
        counts = {"new": 0, "merge": 0, "skip": 0}
        for rec in records:
            counts[store.apply(rec)] += 1
        print(f"{reader.vendor_of(path)}: encoding={enc} added={counts['new']} "
              f"merged={counts['merge']} skipped={counts['skip']}")
    store.save()
    return 0


def cmd_list(args):
    store = Store(args.store)
    for c in store.customers:
        if args.source and not any(s.split(":", 1)[0] == args.source for s in c.sources):
            continue
        print(f"{c.id}\t{c.name}\t{c.email}\t{c.phone}\t{' '.join(c.sources)}")
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(prog="custimport")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("import")
    a.add_argument("store")
    a.add_argument("files", nargs="+")
    a.set_defaults(func=cmd_import)
    b = sub.add_parser("list")
    b.add_argument("store")
    b.add_argument("--source")
    b.set_defaults(func=cmd_list)
    args = p.parse_args(argv)
    return args.func(args)
