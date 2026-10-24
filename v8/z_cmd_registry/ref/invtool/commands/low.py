"""invtool low: items whose stock is below the threshold."""
import sys

from invtool.common import LOW_THRESHOLD, usage_error, parse_int, parse_opts, load
from invtool.registry import command


@command("low", usage="low [--threshold N]", summary="items whose stock is below the threshold")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("low", args, options=("threshold",))
    if pos:
        raise usage_error("low")
    th = parse_int(opts.get("threshold", str(LOW_THRESHOLD)), "threshold")
    items = sorted((it for it in load(data) if it["qty"] < th), key=lambda x: (x["qty"], x["sku"]))
    if not items:
        out.write(f"nothing below {th}\n")
        return 0
    for it in items:
        out.write(f"{it['sku']:<10}{it['qty']:>5}  {it['name']}\n")
    return 0
