"""invtool history: show stock changes of an item."""
import sys

from invtool.common import usage_error, parse_int, parse_opts, load, find, read_history, CommandError
from invtool.registry import command


@command("history", usage="history SKU [--limit N]", summary="show stock changes of an item")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("history", args, options=("limit",))
    if len(pos) != 1:
        raise usage_error("history")
    it = find(load(data), pos[0])
    rows = [h for h in read_history(data) if h[1] == it["sku"]]
    if "limit" in opts:
        n = parse_int(opts["limit"], "limit")
        if n <= 0:
            raise CommandError(f"invalid limit: {n}")
        rows = rows[-n:]
    if not rows:
        out.write(f"no history for {it['sku']}\n")
        return 0
    for seq, _, delta, reason in rows:
        out.write(f"#{seq:<4} {delta:+6d}  {reason}\n")
    return 0
