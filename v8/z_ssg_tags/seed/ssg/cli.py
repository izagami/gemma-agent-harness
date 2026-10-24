"""python3 -m ssg build SRC OUT"""
import argparse
import sys

from ssg import site
from ssg.frontmatter import FrontMatterError


def main(argv=None):
    p = argparse.ArgumentParser(prog="ssg")
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("src")
    b.add_argument("out")
    args = p.parse_args(argv)
    try:
        n = site.build(args.src, args.out)
    except FrontMatterError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(f"wrote {n} file(s)")
    return 0
