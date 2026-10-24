"""invtool move: move an item to another location."""
import sys

from invtool.common import usage_error, parse_opts, load, save, find
from invtool.registry import command


@command("move", usage="move SKU LOCATION", summary="move an item to another location")
def run(args, data):
    out = sys.stdout
    pos, _ = parse_opts("move", args)
    if len(pos) != 2:
        raise usage_error("move")
    items = load(data)
    it = find(items, pos[0])
    loc = pos[1].upper()
    if loc == it["location"]:
        out.write(f"{it['sku']} is already at {loc}\n")
        return 0
    old, it["location"] = it["location"], loc
    save(data, items)
    out.write(f"moved {it['sku']} from {old} to {loc}\n")
    return 0
