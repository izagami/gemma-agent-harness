"""invtool export: write all items to stdout."""
import csv
import io
import json
import sys

from invtool.common import FIELDS, usage_error, fmt_money, parse_opts, load, CommandError
from invtool.registry import command


@command("export", usage="export [--format csv|json|tsv]", summary="write all items to stdout")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("export", args, options=("format",))
    if pos:
        raise usage_error("export")
    fmt = opts.get("format", "csv")
    items = sorted(load(data), key=lambda x: x["sku"])
    if fmt == "json":
        doc = [{"sku": it["sku"], "name": it["name"], "qty": it["qty"], "price": it["price"] / 100,
                "location": it["location"]} for it in items]
        out.write(json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
    elif fmt in ("csv", "tsv"):
        buf = io.StringIO()
        w = csv.writer(buf, delimiter="," if fmt == "csv" else "\t", lineterminator="\n")
        w.writerow(FIELDS)
        for it in items:
            w.writerow([it["sku"], it["name"], it["qty"], fmt_money(it["price"]).replace(",", ""), it["location"]])
        out.write(buf.getvalue())
    else:
        raise CommandError(f"invalid format: {fmt}", 2)
    return 0
