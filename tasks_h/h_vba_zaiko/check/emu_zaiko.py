"""Independent emulation of vba/Module1.bas (在庫評価表) with VBA semantics, used by the hidden check.

trans: list of [date, code, kbn, qty, price] strings (sheet 入出庫 without header), master: list of [code, name, irisu].
kijun: "yyyy/mm/dd". Returns the file as bytes exactly as `Print #` writes it (cp932, CRLF), or None when the macro
exits without writing a file."""
import datetime
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def vtrim(s):            # VBA Trim removes only U+0020
    return s.strip(" ")


def vnum(s):             # Empty cell -> 0
    s = s.strip()
    return float(s) if s else 0.0


def clng(x):             # CLng: round half to even on the exact double
    f = Fraction(x)
    fl = f.numerator // f.denominator
    rem = f - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        fl += 1
    if not -2 ** 31 <= fl < 2 ** 31:
        raise OverflowError("Long overflow")
    return fl


def idiv(a, b):          # \ truncates toward zero
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def vmod(a, b):          # Mod takes the sign of the dividend
    return a - b * idiv(a, b)


def fmt(x, places):      # Format(x, "#,##0" / "#,##0.00"): half away from zero
    q = Decimal(1).scaleb(-places)
    d = Decimal(f"{x:.15g}").quantize(q, ROUND_HALF_UP)
    s = f"{abs(d):,.{places}f}"
    return ("-" + s) if d < 0 else s


def fmt_pct(x):          # Format(x, "0.0%")
    d = (Decimal(f"{x:.15g}") * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(d):.1f}%"


def pdate(s):
    y, m, d = (int(p) for p in s.strip().split("/"))
    return datetime.date(y, m, d)


def lng(x):
    if not -2 ** 31 <= x < 2 ** 31:
        raise OverflowError("Long overflow")
    return x


def report(trans, master, kijun):
    kj = pdate(kijun)
    trans = [(list(r) + [""] * 5)[:5] for r in trans]
    for r in trans:
        if r[0] != "" and vtrim(r[2]) not in ("入庫", "出庫", "調整"):
            return None
    mst = {}
    for r in master:
        r = (list(r) + [""] * 3)[:3]
        c = vtrim(r[0]).upper()
        if c and c not in mst:
            mst[c] = r
    zq, za = {}, {}
    for r in trans:
        if r[0] == "" or pdate(r[0]) > kj:
            continue
        code = vtrim(r[1]).upper()
        if not code:
            continue
        kbn = vtrim(r[2])
        qty = clng(vnum(r[3]))
        if code not in zq:
            zq[code] = 0; za[code] = 0
        if kbn == "入庫":
            za[code] = lng(za[code] + clng(qty * vnum(r[4])))
            zq[code] = lng(zq[code] + qty)
        elif kbn == "出庫":
            if zq[code] <= 0 or qty >= zq[code]:
                cost = za[code]
            else:
                cost = clng(lng(za[code] * qty) / zq[code])
            za[code] -= cost
            zq[code] -= qty
        else:
            zq[code] = lng(zq[code] + qty)
    codes = list(zq)
    n = len(codes)
    grand = 0.0
    for c in codes:
        grand += za[c]
    if grand <= 0:
        return None
    idx = list(range(n))
    for i in range(n - 1):            # the macro's selection sort (swap, so equal values change order)
        k = i
        for j in range(i + 1, n):
            if za[codes[idx[j]]] > za[codes[idx[k]]]:
                k = j
        if k != i:
            idx[i], idx[k] = idx[k], idx[i]
    out = ["基準日\t" + kj.strftime("%Y/%m/%d"),
           "\t".join(["品番", "品名", "入数", "在庫数", "ケース", "バラ", "単価", "評価額", "構成比", "累計", "ランク"])]
    cum = 0.0
    for i in range(n):
        c = codes[idx[i]]
        if c in mst:
            nm = mst[c][1]
            irisu = clng(vnum(mst[c][2]))
        else:
            nm, irisu = "(未登録)", 0
        if irisu <= 0:
            irisu = 1
        q, a = zq[c], za[c]
        tanka = fmt(a / q, 2) if q > 0 else "-"
        cum += a
        rank = "A" if cum / grand <= 0.7 else ("B" if cum / grand <= 0.9 else "C")
        out.append("\t".join([c, nm, str(irisu), str(q), str(idiv(q, irisu)), str(vmod(q, irisu)), tanka,
                              fmt(a, 0), fmt_pct(a / grand), fmt_pct(cum / grand), rank]))
    out.append("\t".join(["合計", f"{n}品目", "", "", "", "", "", fmt(grand, 0), "100.0%"]))
    return "".join(l + "\r\n" for l in out).encode("cp932")
