import argparse
import os
import shlex
import sys
from dataclasses import dataclass

from ts import commands
from ts.config import Config, load
from ts.errors import ConfigError, TsError

DEFAULT_CONFIG = "ts.conf"


@dataclass
class Context:
    config: Config
    data_path: str


def build_parser():
    p = argparse.ArgumentParser(prog="ts")
    p.add_argument("--config", help=f"config file (default: ./{DEFAULT_CONFIG} if it exists)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("add")
    s.add_argument("date")
    s.add_argument("project")
    s.add_argument("duration")
    s.add_argument("note", nargs="*")
    s.set_defaults(fn=commands.cmd_add)
    s = sub.add_parser("list")
    s.add_argument("--project")
    s.set_defaults(fn=commands.cmd_list)
    s = sub.add_parser("total")
    s.add_argument("--project")
    s.set_defaults(fn=commands.cmd_total)
    s = sub.add_parser("invoice")
    s.add_argument("project")
    s.add_argument("--month", required=True)
    s.set_defaults(fn=commands.cmd_invoice)
    return p


BUILTIN = {"add", "list", "total", "invoice"}


def command_index(argv):
    i = 0
    while i < len(argv):
        if argv[i] == "--config":
            i += 2
        elif argv[i].startswith("--config=") or argv[i] in ("-h", "--help"):
            i += 1
        else:
            break
    return i


def explicit_config(argv):
    path = None
    i = 0
    while i < command_index(argv):
        if argv[i] == "--config" and i + 1 < len(argv):
            path = argv[i + 1]
        elif argv[i].startswith("--config="):
            path = argv[i][len("--config="):]
        i += 1
    return path


def load_config(explicit):
    explicit = explicit or os.environ.get("TS_CONFIG") or None
    if explicit:
        return load(explicit)
    if os.path.exists(DEFAULT_CONFIG):
        return load(DEFAULT_CONFIG)
    return Config()


def make_context(config):
    data = config.get("data", "entries.tsv")
    return Context(config, os.path.join(config.base_dir, data))


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        config = load_config(explicit_config(argv))
    except ConfigError as e:
        print(f"error: config: {e}", file=sys.stderr)
        return e.exit_code
    i = command_index(argv)
    aliases = config.section("alias")
    if i < len(argv) and argv[i] in aliases and argv[i] not in BUILTIN:
        argv = argv[:i] + shlex.split(aliases[argv[i]]) + argv[i + 1:]
    args = build_parser().parse_args(argv)
    try:
        ctx = make_context(config)
        args.fn(ctx, args)
    except ConfigError as e:
        print(f"error: config: {e}", file=sys.stderr)
        return e.exit_code
    except TsError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code
    return 0
