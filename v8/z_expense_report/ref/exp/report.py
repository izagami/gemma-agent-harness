"""Monthly report: expenses converted to JPY and grouped by category or day."""
import csv
import io
import json
import os
import re
from decimal import ROUND_HALF_UP, Decimal

MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
DEFAULT_RATES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "rates.json")


class ReportError(Exception):
    pass


def load_rates(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return {k: Decimal(str(v)) for k, v in data["rates"].items()}
    except OSError:
        raise ReportError(f"cannot read rates file: {path}") from None
    except (ValueError, KeyError, TypeError, ArithmeticError):
        raise ReportError(f"invalid rates file: {path}") from None


def to_jpy(e, rates):
    if e.currency not in rates:
        raise ReportError(f"no rate for {e.currency}")
    return int((e.decimal_amount * rates[e.currency]).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def build(expenses, rates, by):
    groups = {}
    for e in expenses:
        key = e.category if by == "category" else e.date
        g = groups.setdefault(key, [0, 0])
        g[0] += 1
        g[1] += to_jpy(e, rates)
    if by == "category":
        order = sorted(groups.items(), key=lambda kv: (-kv[1][1], kv[0]))
    else:
        order = sorted(groups.items())
    return [{"key": k, "count": c, "total_jpy": t} for k, (c, t) in order]


def render(month, by, fmt, groups):
    count = sum(g["count"] for g in groups)
    total = sum(g["total_jpy"] for g in groups)
    if fmt == "json":
        return json.dumps({"month": month, "by": by, "count": count, "total_jpy": total, "groups": groups},
                          ensure_ascii=False, indent=2) + "\n"
    if fmt == "csv":
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["key", "count", "total_jpy"])
        for g in groups:
            w.writerow([g["key"], g["count"], g["total_jpy"]])
        return buf.getvalue()
    if not groups:
        return f"no expenses in {month}\n"
    line = lambda k, t, c: f"{k:<12}{t:>10,}  ({c})"
    out = [f"Report {month} (by {by})"]
    out += [line(g["key"], g["total_jpy"], g["count"]) for g in groups]
    out += ["-" * 22, line("TOTAL", total, count)]
    return "\n".join(out) + "\n"
