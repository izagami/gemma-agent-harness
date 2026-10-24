"""invtool list: list items."""
import sys

from invtool.common import usage_error, parse_opts, load, table, item_row, HEADER, RIGHT, CommandError
from invtool.registry import command


@command("list", usage="list [--location LOC] [--sort sku|name|qty|value]", summary="list items")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("list", args, options=("location", "sort"))
    if pos:
        raise usage_error("list")
    items = load(data)
    if "location" in opts:
        items = [it for it in items if it["location"] == opts["location"].upper()]
    key = opts.get("sort", "sku")
    if key == "sku":
        items.sort(key=lambda x: x["sku"])
    elif key == "name":
        items.sort(key=lambda x: (x["name"].lower(), x["sku"]))
    elif key == "qty":
        items.sort(key=lambda x: (-x["qty"], x["sku"]))
    elif key == "value":
        items.sort(key=lambda x: (-x["qty"] * x["price"], x["sku"]))
    else:
        raise CommandError(f"invalid sort key: {key}", 2)
    if not items:
        out.write("no items\n")
        return 0
    out.write(table([item_row(it) for it in items], HEADER, RIGHT) + "\n")
    out.write(f"{len(items)} item(s)\n")
    return 0
