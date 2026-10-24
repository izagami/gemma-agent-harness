"""python3 -m jwrap [-w WIDTH] [FILE]   (default width 40, FILE '-' or missing = stdin)"""
import argparse
import sys

from .wrap import wrap


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jwrap")
    ap.add_argument("-w", "--width", type=int, default=40)
    ap.add_argument("file", nargs="?", default="-")
    a = ap.parse_args(argv)
    text = sys.stdin.read() if a.file == "-" else open(a.file, encoding="utf-8").read()
    if text.endswith("\n"):
        text = text[:-1]
    try:
        lines = wrap(text, a.width)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    sys.stdout.write("".join(line + "\n" for line in lines))
    return 0
