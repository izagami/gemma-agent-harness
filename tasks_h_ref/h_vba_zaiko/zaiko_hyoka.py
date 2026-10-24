#!/usr/bin/env python3
"""Port of vba/Module1.bas 在庫評価表 (moving average + ABC rank), byte-exact with the macro.

usage: python3 zaiko_hyoka.py <入出庫.csv> <品目.csv> <基準日 yyyy/mm/dd> <out file>"""
import csv, datetime, sys
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction


def read_rows(path):
    with open(path, encoding="cp932", newline="") as f:
        return list(csv.reader(f))[1:]


def cell(row, i):
    return row[i] if i < len(row) else ""


def vba_trim(s):                 # Trim removes ASCII spaces only
    return s.strip(" ")


def num(s):                      # empty cell = 0
    s = s.strip()
    return float(s) if s else 0.0


def clng(x):                     # CLng: banker's rounding on the double's exact value
    fr = Fraction(x)
    q, r = divmod(fr.numerator, fr.denominator)
    r = Fraction(r, fr.denominator)
    if r > Fraction(1, 2) or (r == Fraction(1, 2) and q % 2):
        q += 1
    return q


def vb_idiv(a, b):               # \ truncates toward zero
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def vb_mod(a, b):
    return a - b * vb_idiv(a, b)


def vb_format(x, places):        # Format "#,##0" / "#,##0.00": half away from zero on ~15 significant digits
    d = Decimal(repr(float(f"{x:.15g}"))).quantize(Decimal(1).scaleb(-places), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(d):,.{places}f}"


def vb_pct(x):
    d = (Decimal(f"{x:.15g}") * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(d):.1f}%"


def to_date(s):
    y, m, d = s.strip().split("/")
    return datetime.date(int(y), int(m), int(d))


def main():
    tpath, mpath, kijun_s, out = sys.argv[1:5]
    kijun = to_date(kijun_s)
    trans = read_rows(tpath)
    for row in trans:
        if cell(row, 0) != "" and vba_trim(cell(row, 2)) not in ("入庫", "出庫", "調整"):
            return                       # MsgBox + Exit Sub: no file
    master = {}
    for row in read_rows(mpath):
        code = vba_trim(cell(row, 0)).upper()
        if code and code not in master:
            master[code] = (cell(row, 1), cell(row, 2))
    zq, za = {}, {}                      # dict keeps first-seen order like Scripting.Dictionary
    for row in trans:
        if cell(row, 0) == "" or to_date(cell(row, 0)) > kijun:
            continue
        code = vba_trim(cell(row, 1)).upper()
        if not code:
            continue
        kbn = vba_trim(cell(row, 2))
        qty = clng(num(cell(row, 3)))
        zq.setdefault(code, 0); za.setdefault(code, 0)
        if kbn == "入庫":
            za[code] += clng(qty * num(cell(row, 4)))
            zq[code] += qty
        elif kbn == "出庫":
            cost = za[code] if (zq[code] <= 0 or qty >= zq[code]) else clng(za[code] * qty / zq[code])
            za[code] -= cost
            zq[code] -= qty
        else:
            zq[code] += qty
    codes = list(zq)
    grand = 0.0
    for c in codes:
        grand += za[c]
    if grand <= 0:
        return
    idx = list(range(len(codes)))
    for i in range(len(idx) - 1):        # selection sort exactly as the macro (not stable)
        k = i
        for j in range(i + 1, len(idx)):
            if za[codes[idx[j]]] > za[codes[idx[k]]]:
                k = j
        if k != i:
            idx[i], idx[k] = idx[k], idx[i]
    lines = ["基準日\t" + f"{kijun.year:04d}/{kijun.month:02d}/{kijun.day:02d}",
             "品番\t品名\t入数\t在庫数\tケース\tバラ\t単価\t評価額\t構成比\t累計\tランク"]
    cum = 0.0
    for i in idx:
        c = codes[i]
        if c in master:
            name, irisu = master[c][0], clng(num(master[c][1]))
        else:
            name, irisu = "(未登録)", 0
        if irisu <= 0:
            irisu = 1
        q, a = zq[c], za[c]
        cum += a
        rank = "A" if cum / grand <= 0.7 else "B" if cum / grand <= 0.9 else "C"
        lines.append("\t".join([c, name, str(irisu), str(q), str(vb_idiv(q, irisu)), str(vb_mod(q, irisu)),
                                vb_format(a / q, 2) if q > 0 else "-", vb_format(a, 0), vb_pct(a / grand),
                                vb_pct(cum / grand), rank]))
    lines.append(f"合計\t{len(codes)}品目\t\t\t\t\t\t{vb_format(grand, 0)}\t100.0%")
    with open(out, "wb") as f:
        f.write("".join(l + "\r\n" for l in lines).encode("cp932"))


main()
