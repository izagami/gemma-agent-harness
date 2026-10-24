"""invtool value: stock value in total or per location."""
import sys

from invtool.common import usage_error, fmt_money, parse_opts, load, table, CommandError
from invtool.registry import command


@command("value", usage="value [--by location]", summary="stock value in total or per location")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("value", args, options=("by",))
    if pos:
        raise usage_error("value")
    items = load(data)
    by = opts.get("by")
    if by is None:
        total = sum(it["qty"] * it["price"] for it in items)
        out.write(f"total: {fmt_money(total)} ({sum(it['qty'] for it in items)} units)\n")
    elif by == "location":
        acc = {}
        for it in items:
            a = acc.setdefault(it["location"], [0, 0])
            a[0] += it["qty"]
            a[1] += it["qty"] * it["price"]
        rows = [[loc, u, fmt_money(v)] for loc, (u, v) in sorted(acc.items(), key=lambda kv: (-kv[1][1], kv[0]))]
        rows.append(["TOTAL", sum(r[1] for r in rows), fmt_money(sum(v for _, v in acc.values()))])
        out.write(table(rows, ["LOC", "UNITS", "VALUE"], (1, 2)) + "\n")
    else:
        raise CommandError(f"invalid grouping: {by}", 2)
    return 0
