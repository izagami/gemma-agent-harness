#!/usr/bin/env python3
"""Port of vba/Module1.bas (支払予定表).  usage: pay_schedule.py <請求.csv> <出力ファイル>"""
import calendar
import csv
import re
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

KIJUN = date(2026, 4, 1)


def dateserial(y, m, d):
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return date(y, m, 1) + timedelta(days=d - 1)


def dateadd_month(x, n):
    total = x.year * 12 + (x.month - 1) + n
    y, m = divmod(total, 12)
    return date(y, m + 1, min(x.day, calendar.monthrange(y, m + 1)[1]))


def datediff_ww(a, b):
    # weeks start on Sunday; count week boundaries crossed (date.weekday(): Monday=0 ... Sunday=6)
    sa = a - timedelta(days=(a.weekday() + 1) % 7)
    sb = b - timedelta(days=(b.weekday() + 1) % 7)
    return (sb - sa).days // 7


def vba_val(s):
    s = re.sub(r"[ \t\n]", "", s)
    m = re.match(r"[+-]?(?:[0-9]+\.?[0-9]*|\.[0-9]+)(?:[eE][+-]?[0-9]+)?", s)
    return float(m.group()) if m else 0.0


def vba_like(s, pattern):
    return re.fullmatch(".*".join(map(re.escape, pattern.split("*"))), s) is not None


def fmt_yen(s):
    d = Decimal(s.strip()).quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + "{:,}".format(abs(int(d)))


def main(src, dst):
    with open(src, encoding="cp932", newline="") as f:
        rows = list(csv.reader(f))[1:]
    lines = ["請求番号\t請求日\t締め日\t支払予定日\t週\t金額"]
    for row in rows:
        row += [""] * (5 - len(row))
        no = row[0]
        p = row[1].strip(" ").split("/")
        dt = None
        if len(p) == 3 and all(x.strip(" ").isdigit() and x.strip(" ").isascii() for x in p):
            y, m, d = (int(x) for x in p)
            dt = dateserial(y, m, d)
            if (dt.year, dt.month, dt.day) != (y, m, d):
                dt = None
        if dt is None:
            lines.append(no + "\tERROR 請求日不正")
            continue
        cond = row[3].strip(" ")
        if cond == "末締め翌月末払い":
            closing = dateserial(y, m + 1, 0)
            pay = dateserial(closing.year, closing.month + 2, 0)
        elif vba_like(cond, "末締め翌々月*日払い"):
            closing = dateserial(y, m + 1, 0)
            pay = dateserial(closing.year, closing.month + 2, int(vba_val(cond[6:])))   # Mid(cond, 7)
        elif vba_like(cond, "*日締め翌月*日払い") or vba_like(cond, "*日締め翌月末払い"):
            n = int(vba_val(cond))
            closing = dateserial(y, m, n) if d <= n else dateserial(y, m + 1, n)
            if "翌月末" in cond:
                pay = dateserial(closing.year, closing.month + 2, 0)
            else:
                pay = dateserial(closing.year, closing.month + 1, int(vba_val(cond[cond.find("翌月") + 2:])))
        elif vba_like(cond, "納品後*日"):
            closing = dt
            pay = dt + timedelta(days=int(vba_val(cond[3:])))                       # Mid(cond, 4)
        elif vba_like(cond, "*ヶ月後"):
            closing = dt
            pay = dateadd_month(dt, int(vba_val(cond)))
        else:
            lines.append(no + "\tERROR 支払条件不明")
            continue
        wd = pay.isoweekday()                                                       # Weekday(pay, vbMonday)
        if wd == 6:
            pay -= timedelta(days=1)
        elif wd == 7:
            pay -= timedelta(days=2)
        lines.append("\t".join([no, dt.strftime("%Y/%m/%d"), closing.strftime("%Y/%m/%d"),
                                pay.strftime("%Y/%m/%d") + " (" + "月火水木金土日"[pay.weekday()] + ")",
                                str(datediff_ww(KIJUN, pay)), fmt_yen(row[4])]))
    with open(dst, "w", encoding="cp932", newline="") as f:
        f.write("".join(l + "\r\n" for l in lines))


if __name__ == "__main__":
    main(*sys.argv[1:3])
