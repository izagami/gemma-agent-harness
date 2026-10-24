"""invtool add: add a new item."""
import sys

from invtool.common import DEFAULT_LOCATION, usage_error, parse_money, fmt_money, parse_int, parse_opts, load, save, append_history, CommandError
from invtool.registry import command


@command("add", usage="add SKU NAME QTY PRICE [--location LOC]", summary="add a new item")
def run(args, data):
    out = sys.stdout
    pos, opts = parse_opts("add", args, options=("location",))
    if len(pos) != 4:
        raise usage_error("add")
    sku, name, qty, price = pos
    sku = sku.upper()
    if not sku.replace("-", "").isalnum():
        raise CommandError(f"invalid SKU: {sku}")
    if not name.strip():
        raise CommandError("name must not be empty")
    qty = parse_int(qty, "quantity")
    if qty < 0:
        raise CommandError(f"invalid quantity: {qty}")
    cents = parse_money(price)
    if cents < 0:
        raise CommandError(f"invalid price: {price}")
    items = load(data)
    if any(it["sku"] == sku for it in items):
        raise CommandError(f"SKU {sku} already exists")
    loc = opts.get("location", DEFAULT_LOCATION).upper()
    items.append({"sku": sku, "name": name.strip(), "qty": qty, "price": cents, "location": loc})
    save(data, items)
    if qty:
        append_history(data, sku, qty, "initial stock")
    out.write(f"added {sku} ({qty} x {fmt_money(cents)}) at {loc}\n")
    return 0
