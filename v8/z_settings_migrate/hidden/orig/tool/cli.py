"""python3 -m tool [--config INI] [--set KEY=VALUE ...] COMMAND ...

Commands:
  scan ROOT            list files that would be backed up
  backup ROOT OUTDIR   write OUTDIR/<backup.name>.manifest
  report ROOT          size report
  show-config          effective settings, one "key = value" per line
"""
import argparse
import sys

from tool import legacy_settings, log, manifest, report, scanner


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
    legacy_settings.clear_overrides()
    try:
        legacy_settings.reload(args.config)
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for item in args.set:
        if "=" not in item:
            print("error: --set expects KEY=VALUE", file=sys.stderr)
            return 2
        k, v = item.split("=", 1)
        legacy_settings.set_override(k.strip(), v)
    try:
        if args.cmd == "show-config":
            for k, v in legacy_settings.items():
                print(f"{k} = {v}")
            return 0
        entries = scanner.scan(args.root)
        if args.cmd == "scan":
            for e in entries:
                print(f"{e.size:>10}  {e.path}")
        elif args.cmd == "backup":
            path = manifest.write(entries, args.outdir)
            print(f"wrote {path} ({len(entries)} files)")
        elif args.cmd == "report":
            sys.stdout.write(report.render(entries))
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    log.info("done")
    return 0
