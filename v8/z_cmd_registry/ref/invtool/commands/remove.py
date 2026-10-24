"""invtool remove: delete an item."""
import sys

from invtool.common import usage_error, parse_opts, load, save, find, CommandError
from invtool.registry import command


@command("remove", usage="remove SKU [--force]", summary="delete an item")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("remove", args, flags=("force",))
    if len(pos) != 1:
        raise usage_error("remove")
    items = load(data)
    it = find(items, pos[0])
    if it["qty"] > 0 and not opts.get("force"):
        raise CommandError(f"{it['sku']} still has {it['qty']} in stock (use --force)")
    items.remove(it)
    save(data, items)
    out.write(f"removed {it['sku']}\n")
    return 0
