"""python3 -m vsort sort [--desc] FILE | max FILE | cmp A B"""
import argparse
import sys

from .compare import compare, sort_versions
from .parse import InvalidVersion, parse


def read_versions(path):
    good, bad = [], []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            try:
                good.append(parse(line))
            except InvalidVersion:
                bad.append(line.strip())
    return good, bad


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vsort")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sort"); s.add_argument("--desc", action="store_true"); s.add_argument("file")
    m = sub.add_parser("max"); m.add_argument("file")
    c = sub.add_parser("cmp"); c.add_argument("a"); c.add_argument("b")
    a = ap.parse_args(argv)
    if a.cmd == "cmp":
        try:
            print({-1: "<", 0: "=", 1: ">"}[compare(a.a, a.b)])
        except InvalidVersion as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        return 0
    good, bad = read_versions(a.file)
    for b in bad:
        print(f"invalid version: {b}", file=sys.stderr)
    if a.cmd == "sort":
        for v in sort_versions(good, reverse=a.desc):
            print(v.text)
    elif good:
        print(sort_versions(good)[-1].text)
    return 1 if bad else 0
