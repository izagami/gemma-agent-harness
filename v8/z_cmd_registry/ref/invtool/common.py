"""Helpers shared by the commands.

Data file: CSV with header sku,name,qty,price,location (price in yen with 2 decimals, e.g. 120.50).
History:   <data file>.history, one line per stock change: "<seq>\t<sku>\t<delta>\t<reason>".
"""
import csv
import os

from invtool import registry
from invtool.registry import CommandError

FIELDS = ["sku", "name", "qty", "price", "location"]
DEFAULT_LOCATION = "MAIN"
LOW_THRESHOLD = 5


def usage_error(cmd):
    return CommandError(f"usage: invtool {registry.get(cmd).usage}", 2)


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
