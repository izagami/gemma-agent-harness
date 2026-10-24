"""invtool show: show one item."""
import sys

from invtool.common import usage_error, fmt_money, parse_opts, load, find
from invtool.registry import command


@command("show", usage="show SKU", summary="show one item")
def run(args, data):
    out = sys.stdout
    pos, _ = parse_opts("show", args)
    if len(pos) != 1:
        raise usage_error("show")
    it = find(load(data), pos[0])
    for label, value in [("sku", it["sku"]), ("name", it["name"]), ("qty", it["qty"]),
                         ("price", fmt_money(it["price"])), ("value", fmt_money(it["qty"] * it["price"])),
                         ("location", it["location"])]:
        out.write(f"{label + ':':<10}{value}\n")
    return 0
