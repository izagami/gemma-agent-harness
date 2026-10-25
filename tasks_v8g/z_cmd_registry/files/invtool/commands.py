"""All invtool commands.

Data file: CSV with header sku,name,qty,price,location (price in yen with 2 decimals, e.g. 120.50).
History:   <data file>.history, one line per stock change: "<seq>\t<sku>\t<delta>\t<reason>".
"""
import csv
import io
import json
import os
import sys

FIELDS = ["sku", "name", "qty", "price", "location"]
DEFAULT_LOCATION = "MAIN"
LOW_THRESHOLD = 5

USAGE = {
    "add": "add SKU NAME QTY PRICE [--location LOC]",
    "adjust": "adjust SKU DELTA [--reason TEXT]",
    "export": "export [--format csv|json|tsv]",
    "help": "help [COMMAND]",
    "history": "history SKU [--limit N]",
    "list": "list [--location LOC] [--sort sku|name|qty|value]",
    "low": "low [--threshold N]",
    "move": "move SKU LOCATION",
    "remove": "remove SKU [--force]",
    "search": "search TERM",
    "show": "show SKU",
    "value": "value [--by location]",
}
SUMMARY = {
    "add": "add a new item",
    "adjust": "change the stock of an item by DELTA",
    "export": "write all items to stdout",
    "help": "show help",
    "history": "show stock changes of an item",
    "list": "list items",
    "low": "items whose stock is below the threshold",
    "move": "move an item to another location",
    "remove": "delete an item",
    "search": "find items by sku or name",
    "show": "show one item",
    "value": "stock value in total or per location",
}


class CommandError(Exception):
    def __init__(self, msg, code=1):
        super().__init__(msg)
        self.code = code


def usage_error(cmd):
    return CommandError(f"usage: invtool {USAGE[cmd]}", 2)


# ---------------------------------------------------------------- helpers

def parse_money(text):
    text = text.strip()
    neg = text.startswith("-")
    if neg:
        text = text[1:]
    whole, _, frac = text.partition(".")
    if not whole.isdigit() or (frac and (not frac.isdigit() or len(frac) > 2)):
        raise CommandError(f"invalid price: {text}")
    cents = int(whole) * 100 + int((frac + "00")[:2])
    return -cents if neg else cents


def fmt_money(cents):
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    whole = f"{cents // 100:,}"
    return f"{sign}{whole}.{cents % 100:02d}"


def parse_int(text, what):
    try:
        return int(text)
    except ValueError:
        raise CommandError(f"invalid {what}: {text}") from None


def parse_opts(cmd, args, flags=(), options=()):
    """Split args into positionals and options. flags: names without value; options: names with a value."""
    pos, opts = [], {}
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            pos.extend(args[i + 1:])
            break
        if a.startswith("--"):
            name, eq, val = a[2:].partition("=")
            if name in flags and not eq:
                opts[name] = True
            elif name in options:
                if not eq:
                    i += 1
                    if i >= len(args):
                        raise usage_error(cmd)
                    val = args[i]
                opts[name] = val
            else:
                raise CommandError(f"unknown option --{name} for {cmd}", 2)
        else:
            pos.append(a)
        i += 1
    return pos, opts


def load(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    items = []
    for r in rows:
        items.append({"sku": r["sku"], "name": r["name"], "qty": int(r["qty"]),
                      "price": parse_money(r["price"]), "location": r["location"] or DEFAULT_LOCATION})
    return items


def save(path, items):
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        for it in sorted(items, key=lambda x: x["sku"]):
            w.writerow([it["sku"], it["name"], it["qty"], fmt_money(it["price"]).replace(",", ""), it["location"]])


def find(items, sku):
    sku = sku.upper()
    for it in items:
        if it["sku"] == sku:
            return it
    raise CommandError(f"unknown SKU {sku}")


def history_path(path):
    return path + ".history"


def read_history(path):
    p = history_path(path)
    if not os.path.exists(p):
        return []
    out = []
    with open(p, encoding="utf-8") as f:
        for line in f:
            seq, sku, delta, reason = line.rstrip("\n").split("\t", 3)
            out.append((int(seq), sku, int(delta), reason))
    return out


def append_history(path, sku, delta, reason):
    seq = len(read_history(path)) + 1
    with open(history_path(path), "a", encoding="utf-8") as f:
        f.write(f"{seq}\t{sku}\t{delta}\t{reason}\n")


def table(rows, header, right=()):
    widths = [max(len(str(r[i])) for r in [header] + rows) for i in range(len(header))]
    lines = []
    for r in [header] + rows:
        cells = [str(c).rjust(widths[i]) if i in right else str(c).ljust(widths[i]) for i, c in enumerate(r)]
        lines.append("  ".join(cells).rstrip())
    return "\n".join(lines)


def item_row(it):
    return [it["sku"], it["name"], it["qty"], fmt_money(it["price"]), fmt_money(it["qty"] * it["price"]), it["location"]]


HEADER = ["SKU", "NAME", "QTY", "PRICE", "VALUE", "LOC"]
RIGHT = (2, 3, 4)


# ---------------------------------------------------------------- dispatcher

def run(cmd, args, data):
    out = sys.stdout
    try:
        if cmd == "help":
            pos, _ = parse_opts("help", args)
            if len(pos) > 1:
                raise usage_error("help")
            if pos:
                name = pos[0]
                if name not in USAGE:
                    raise CommandError(f"unknown command '{name}'", 2)
                out.write(f"usage: invtool {USAGE[name]}\n\n{SUMMARY[name]}\n")
            else:
                out.write("usage: invtool [--data PATH] COMMAND [ARGS...]\n\ncommands:\n")
                for name in sorted(USAGE):
                    out.write(f"  {name:<10}{SUMMARY[name]}\n")
            return 0

        elif cmd == "list":
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

        elif cmd == "show":
            pos, _ = parse_opts("show", args)
            if len(pos) != 1:
                raise usage_error("show")
            it = find(load(data), pos[0])
            for label, value in [("sku", it["sku"]), ("name", it["name"]), ("qty", it["qty"]),
                                 ("price", fmt_money(it["price"])), ("value", fmt_money(it["qty"] * it["price"])),
                                 ("location", it["location"])]:
                out.write(f"{label + ':':<10}{value}\n")
            return 0

        elif cmd == "add":
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

        elif cmd == "remove":
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

        elif cmd == "adjust":
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

        elif cmd == "move":
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

        elif cmd == "value":
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

        elif cmd == "low":
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

        elif cmd == "search":
            pos, _ = parse_opts("search", args)
            if len(pos) != 1 or not pos[0].strip():
                raise usage_error("search")
            term = pos[0].strip().lower()
            hits = [it for it in load(data) if term in it["sku"].lower() or term in it["name"].lower()]
            if not hits:
                out.write(f"no match for '{pos[0].strip()}'\n")
                return 1
            out.write(table([item_row(it) for it in hits], HEADER, RIGHT) + "\n")
            return 0

        elif cmd == "export":
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

        elif cmd == "history":
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

        else:
            raise CommandError(f"unknown command '{cmd}' (try: invtool help)", 2)
    except CommandError as e:
        print(f"error: {e}", file=sys.stderr)
        return e.code
