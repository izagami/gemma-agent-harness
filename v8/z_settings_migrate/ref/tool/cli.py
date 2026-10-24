"""python3 -m tool [--config INI] [--set KEY=VALUE ...] COMMAND ...

Commands:
  scan ROOT            list files that would be backed up
  backup ROOT OUTDIR   write OUTDIR/<backup.name>.manifest
  report ROOT          size report
  show-config          effective settings, one "key = value" per line
"""
import argparse
import sys

from tool import log, manifest, report, scanner
from tool.settings import Settings


def build_parser():
    p = argparse.ArgumentParser(prog="tool")
    p.add_argument("--config")
    p.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("scan")
    s.add_argument("root")
    b = sub.add_parser("backup")
    b.add_argument("root")
    b.add_argument("outdir")
    r = sub.add_parser("report")
    r.add_argument("root")
    sub.add_parser("show-config")
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    overrides, bad = {}, False
    for item in args.set:
        if "=" not in item:
            bad = True
            break
        k, v = item.split("=", 1)
        overrides[k.strip()] = v
    try:
        settings = Settings.load(args.config, overrides=overrides)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if bad:
        print("error: --set expects KEY=VALUE", file=sys.stderr)
        return 2
    try:
        if args.cmd == "show-config":
            for k, v in settings.items():
                print(f"{k} = {v}")
            return 0
        entries = scanner.scan(args.root, settings)
        if args.cmd == "scan":
            for e in entries:
                print(f"{e.size:>10}  {e.path}")
        elif args.cmd == "backup":
            path = manifest.write(entries, args.outdir, settings)
            print(f"wrote {path} ({len(entries)} files)")
        elif args.cmd == "report":
            sys.stdout.write(report.render(entries, settings))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    log.info("done", settings)
    return 0
