"""invtool search: find items by sku or name."""
import sys

from invtool.common import usage_error, parse_opts, load, table, item_row, HEADER, RIGHT
from invtool.registry import command


@command("search", usage="search TERM", summary="find items by sku or name")
def run(args, data):
    out = sys.stdout
    pos, _ = parse_opts("search", args)
    if len(pos) != 1 or not pos[0].strip():
        raise usage_error("search")
    term = pos[0].strip().lower()
    hits = [it for it in load(data) if term in it["sku"].lower() or term in it["name"].lower()]
    if not hits:
        out.write(f"no match for '{pos[0].strip()}'\n")
        return 1
    out.write(table([item_row(it) for it in hits], HEADER, RIGHT) + "\n")
    return 0
