"""python3 -m shop replay DATA_DIR SCENARIO.jsonl"""
import argparse
import sys

from shop.errors import ShopError
from shop.service import Service


def main(argv=None):
    p = argparse.ArgumentParser(prog="shop")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("replay", help="replay a scenario and print its reports")
    r.add_argument("data_dir")
    r.add_argument("scenario")
    args = p.parse_args(argv)
    try:
        svc = Service.from_dir(args.data_dir)
        svc.replay(args.scenario, sys.stdout)
    except ShopError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    return 0
