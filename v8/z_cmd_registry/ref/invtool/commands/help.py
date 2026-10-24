"""invtool help: show help."""
import sys

from invtool import registry
from invtool.common import usage_error, parse_opts, CommandError
from invtool.registry import command


@command("help", usage="help [COMMAND]", summary="show help")
def run(args, data):
    out = sys.stdout
    pos, _ = parse_opts("help", args)
    if len(pos) > 1:
        raise usage_error("help")
    if pos:
        name = pos[0]
        cmd = registry.get(name)
        if cmd is None:
            raise CommandError(f"unknown command '{name}'", 2)
        out.write(f"usage: invtool {cmd.usage}\n\n{cmd.summary}\n")
    else:
        out.write("usage: invtool [--data PATH] COMMAND [ARGS...]\n\ncommands:\n")
        for c in registry.all_commands():
            out.write(f"  {c.name:<10}{c.summary}\n")
    return 0
