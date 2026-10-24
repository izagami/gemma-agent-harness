#!/usr/bin/env python3
"""usage: report.py --month YYYY-MM [--data DIR] [--config DIR] [--detail REGION] [--out FILE]"""
import argparse
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from salesrep.config import load_config  # noqa: E402
from salesrep.report import build_report  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description="monthly sales report by region")
    ap.add_argument("--month", required=True)
    ap.add_argument("--data", default=os.path.join(HERE, "data"))
    ap.add_argument("--config", default=os.path.join(HERE, "config"))
    ap.add_argument("--detail", metavar="REGION")
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", a.month):
        ap.error("--month must be YYYY-MM")
    cfg = load_config(a.config)
    try:
        text = build_report(cfg, a.data, a.month, a.detail)
    except KeyError as e:
        print(f"unknown region: {e.args[0]}", file=sys.stderr)
        return 2
    if a.out:
        os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
