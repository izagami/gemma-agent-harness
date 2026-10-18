import argparse
import os
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
    return p


def load_config(explicit):
    if explicit:
        return load(explicit)
    if os.path.exists(DEFAULT_CONFIG):
        return load(DEFAULT_CONFIG)
    return Config()


def make_context(config):
    data = config.get("data", "entries.tsv")
    return Context(config, os.path.join(config.base_dir, data))


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        ctx = make_context(load_config(args.config))
        args.fn(ctx, args)
    except ConfigError as e:
        print(f"error: config: {e}", file=sys.stderr)
        return e.exit_code
    except TsError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.exit_code
    return 0
