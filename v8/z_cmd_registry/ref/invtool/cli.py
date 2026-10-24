"""Entry point: global options, then dispatch through the command registry."""
import sys

from invtool import registry

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
    cmd = registry.get(args[0])
    try:
        if cmd is None:
            raise registry.CommandError(f"unknown command '{args[0]}' (try: invtool help)", 2)
        return cmd.func(args[1:], data)
    except registry.CommandError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
