"""invtool adjust: change the stock of an item by DELTA."""
import sys

from invtool.common import LOW_THRESHOLD, usage_error, parse_int, parse_opts, load, save, find, append_history, CommandError
from invtool.registry import command


@command("adjust", usage="adjust SKU DELTA [--reason TEXT]", summary="change the stock of an item by DELTA")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("adjust", args, options=("reason",))
    if len(pos) != 2:
        raise usage_error("adjust")
    items = load(data)
    it = find(items, pos[0])
    delta = parse_int(pos[1], "delta")
    if delta == 0:
        raise CommandError("delta must not be 0")
    if it["qty"] + delta < 0:
        raise CommandError(f"not enough stock: {it['sku']} has {it['qty']}")
    it["qty"] += delta
    save(data, items)
    reason = opts.get("reason", "adjust").replace("\t", " ").replace("\n", " ")
    append_history(data, it["sku"], delta, reason)
    out.write(f"{it['sku']}: {it['qty'] - delta} -> {it['qty']}\n")
    if it["qty"] < LOW_THRESHOLD:
        print(f"warning: {it['sku']} is low on stock ({it['qty']})", file=sys.stderr)
    return 0
