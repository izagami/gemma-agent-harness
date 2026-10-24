"""Entry point: global options, then hand over to the command implementation."""
import sys

from invtool import commands

DEFAULT_DATA = "data/inventory.csv"


def main(argv):
    data = DEFAULT_DATA
    args = list(argv)
    while args and args[0].startswith("--data"):
        opt = args.pop(0)
        if opt == "--data":
            if not args:
                print("error: --data needs a value", file=sys.stderr)
                return 2
            data = args.pop(0)
        elif opt.startswith("--data="):
            data = opt[len("--data="):]
        else:
            print(f"error: unknown option {opt}", file=sys.stderr)
            return 2
    if not args:
        args = ["help"]
    return commands.run(args[0], args[1:], data)
