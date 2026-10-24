"""Command line.

  python3 -m docrender render FILE            HTML of FILE on stdout
  python3 -m docrender batch FILE... -o DIR   DIR/<name>.html for every FILE (name = file name without extension)

Input files are UTF-8.  Exit status: 0 ok, 1 when an input file cannot be read, 2 usage error.
"""
import argparse
import os
import sys

from docrender.renderer import render


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def main(argv=None):
    p = argparse.ArgumentParser(prog="docrender")
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("file")
    b = sub.add_parser("batch")
    b.add_argument("files", nargs="+")
    b.add_argument("-o", "--out", required=True)
    args = p.parse_args(argv)
    try:
        if args.cmd == "render":
            sys.stdout.write(render(read(args.file)))
            return 0
        os.makedirs(args.out, exist_ok=True)
        for path in args.files:
            name = os.path.splitext(os.path.basename(path))[0]
            with open(os.path.join(args.out, name + ".html"), "w", encoding="utf-8") as f:
                f.write(render(read(path)))
            print(f"wrote {os.path.join(args.out, name + '.html')}")
        return 0
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
