"""python3 -m buildorder DEPSFILE [TARGET ...]"""
import sys

from .graph import load
from .order import CycleError, build_order


def main(argv):
    if not argv:
        print("usage: python3 -m buildorder DEPSFILE [TARGET ...]", file=sys.stderr)
        return 1
    try:
        graph = load(argv[0])
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    try:
        order = build_order(graph, argv[1:])
    except KeyError as e:
        print(f"error: unknown target {e.args[0]}", file=sys.stderr)
        return 1
    except CycleError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    for n in order:
        print(n)
    return 0
