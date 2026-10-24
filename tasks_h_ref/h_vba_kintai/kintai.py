#!/usr/bin/env python3
"""Port of vba/Module1.bas 勤怠集計, byte-exact with the macro.

usage: python3 kintai.py <勤怠.csv> <支給月 yyyymm> <out file>"""
import csv, datetime, math, re, sys
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

AAA = ["月", "火", "水", "木", "金", "土", "日"]


def cell(row, i):
    return row[i] if i < len(row) else ""


def to_date(s):                       # IsDate + value; None when not a date
    m = re.fullmatch(r"\s*(\d{1,4})/(\d{1,2})/(\d{1,2})\s*", s)
    if not m:
        return None
    try:
        return datetime.date(*map(int, m.groups()))
    except ValueError:
        return None


def date_serial(y, m, d):             # DateSerial rolls months over
    y, m = y + (m - 1) // 12, (m - 1) % 12 + 1
    return datetime.date(y, m, 1) + datetime.timedelta(days=d - 1)


def cround(x):                        # CLng / assignment to Long: banker's rounding
    fr = Fraction(x)
    q, r = divmod(fr.numerator, fr.denominator)
    if 2 * r > fr.denominator or (2 * r == fr.denominator and q % 2):
        q += 1
    return q


def val(s):                           # VBA Val
    s = s.replace(" ", "").replace("\t", "")
    m = re.match(r"[+-]?(\d+\.?\d*|\.\d+)", s)
    return float(m.group(0)) if m else 0.0


def vb_div(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def fmt0(x):                          # Format(x, "#,##0"): half away from zero
    d = Decimal(f"{x:.15g}").quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(d):,.0f}"


def hm(mins):
    return f"{vb_div(mins, 60)}:{mins - 60 * vb_div(mins, 60):02d}"


def overlap(a1, a2, b1, b2):
    return max(0, min(a2, b2) - max(a1, b1))


def main():
    src, target, out = sys.argv[1:4]
    y, m = int(target[:4]), int(target[4:6])
    d_from, d_to = date_serial(y, m - 1, 16), date_serial(y, m, 15)
    with open(src, encoding="cp932", newline="") as f:
        rows = list(csv.reader(f))[1:]
    names, recs = {}, []
    for row in rows:
        d = to_date(cell(row, 0))
        if d is None or d < d_from or d > d_to:
            continue
        if cell(row, 1).strip(" ") == "" or cell(row, 3) == "" or cell(row, 4) == "":
            continue
        t1, t2 = [tuple(map(int, cell(row, c).split(":"))) for c in (3, 4)]
        st, en = t1[0] * 60 + t1[1], t2[0] * 60 + t2[1]
        if en <= st:
            en += 1440
        brk = cround(val(cell(row, 5)))
        wk = vb_div(en - st - brk, 15) * 15
        if wk <= 0:
            continue
        ot = wk - 480 if wk > 480 else 0
        nt = overlap(st, en, 0, 300) + overlap(st, en, 1320, 1740)
        w = 1100 if cell(row, 6) == "" else cround(float(cell(row, 6)))
        if d.weekday() in (5, 6):
            w += 100
        pay = wk * w / 60 + ot * w * 0.25 / 60 + nt * w * 0.25 / 60
        key = "%05d" % cround(float(cell(row, 1)))
        names.setdefault(key, cell(row, 2).strip(" "))
        recs.append((key, d, t1, t2, brk, wk, ot, nt, pay))
    if not names:
        return
    lines = [f"集計期間\t{d_from:%Y/%m/%d}\t{d_to:%Y/%m/%d}", "社員番号\t氏名\t日付\t出勤\t退勤\t休憩\t実働\t残業\t深夜\t日額"]
    grand = 0
    for key, name in names.items():
        days = swk = sot = snt = 0
        tot = 0.0
        for k, d, t1, t2, brk, wk, ot, nt, pay in recs:
            if k == key:
                lines.append(f"{key}\t{name}\t{d.month}/{d.day}({AAA[d.weekday()]})\t{t1[0]}:{t1[1]:02d}\t"
                             f"{t2[0]}:{t2[1]:02d}\t{brk}\t{hm(wk)}\t{hm(ot)}\t{hm(nt)}\t{fmt0(pay)}")
                days += 1; swk += wk; sot += ot; snt += nt; tot += pay
        lines.append(f"{key}\t{name}\t計\t{days}日\t\t\t{hm(swk)}\t{hm(sot)}\t{hm(snt)}\t{fmt0(math.floor(tot))}")
        grand += math.floor(tot)
    lines.append(f"合計\t{len(names)}名" + "\t" * 8 + fmt0(grand))
    with open(out, "wb") as f:
        f.write("".join(l + "\r\n" for l in lines).encode("cp932"))


main()
