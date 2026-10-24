"""Independent emulation of vba/Module1.bas (VBA semantics), used by the hidden check.

rows: list of [date, name, item, qty, price, rate] strings as Excel exports them (cp932 CSV, row 1 = header).
Returns the report as bytes exactly as `Print #` writes it (cp932, CRLF after every line)."""
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def vtrim(s):            # VBA Trim: only U+0020
    return s.strip(" ")


def vnum(s):             # an empty cell is Empty -> 0 in arithmetic
    s = s.strip()
    return float(s) if s else 0.0


def clng(x):             # CLng: round half to even on the exact double
    f = Fraction(x)
    fl = f.numerator // f.denominator
    rem = f - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        fl += 1
    return fl


def vround0(x):          # Round(x, 0): banker's
    return clng(x)


def idiv(a, b):          # VBA \ on Longs: truncates toward zero
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def vmod(a, b):          # VBA Mod: sign of the dividend
    return a - b * idiv(a, b)


def fmt_int(x):          # Format(x, "#,##0") : arithmetic rounding (half away from zero)
    d = Decimal(f"{x:.15g}").quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(int(d)):,}"


def fmt_pct(x):          # Format(x, "0.0%")
    d = (Decimal(f"{x:.15g}") * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(d):.1f}%"


def yyyymm(cell):
    p = cell.strip().split("/")
    if len(p) != 3:
        return ""
    return f"{int(p[0]):04d}{int(p[1]):02d}"


def report(rows, target):
    acc = {}                       # insertion ordered like Scripting.Dictionary
    grand, scnt, sqty = 0.0, 0, 0
    for row in rows:
        row = (row + [""] * 6)[:6]
        nm = vtrim(row[1])
        if not nm or yyyymm(row[0]) != target:
            continue
        qty = clng(vnum(row[3]))
        amt = clng(qty * vnum(row[4]) * (1 - vnum(row[5])))
        a = acc.setdefault(nm, [0, 0, 0.0])
        a[0] += 1; a[1] += qty; a[2] += amt
        grand += amt; scnt += 1; sqty += qty
    if not acc:
        return None
    # the macro's bubble sort swaps neighbours when tot(j) <= tot(j+1) (equal totals are swapped too)
    order = list(acc)
    last = len(order) - 1
    while last > 0:
        for j in range(last):
            if acc[order[j]][2] <= acc[order[j + 1]][2]:
                order[j], order[j + 1] = order[j + 1], order[j]
        last -= 1
    out = ["\t".join(["担当者", "件数", "数量", "ケース", "バラ", "売上", "平均", "構成比"])]
    for k in order:
        c, q, t = acc[k]
        out.append("\t".join([k, str(c), str(q), str(idiv(q, 12)), str(vmod(q, 12)), fmt_int(t),
                              fmt_int(vround0(t / c)), fmt_pct(t / grand)]))
    out.append("\t".join(["合計", str(scnt), str(sqty), str(idiv(sqty, 12)), str(vmod(sqty, 12)), fmt_int(grand),
                          fmt_int(vround0(grand / scnt)), "100.0%"]))
    return "".join(l + "\r\n" for l in out).encode("cp932")
