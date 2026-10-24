"""Independent emulation of vba/Module1.bas (支払予定表) with VBA date semantics.
rows: lists of cell texts (A..E). Returns the output file bytes (cp932, CRLF)."""
import datetime as dtm
import re
from decimal import Decimal, ROUND_HALF_UP

KIJUN = dtm.date(2026, 4, 1)
EPOCH_SUNDAY = dtm.date(1899, 12, 31)          # a Sunday
WEEKDAY_JA = "月火水木金土日"                    # date.weekday(): Monday = 0


def date_serial(y, m, d):
    """DateSerial: months and days outside their range roll over (day 0 = last day of the previous month)."""
    y2, m2 = y + (m - 1) // 12, (m - 1) % 12 + 1
    return dtm.date(y2, m2, 1) + dtm.timedelta(days=d - 1)


def add_months(x, n):
    """DateAdd("m"): same day number, clamped to the end of the target month."""
    first = date_serial(x.year, x.month + n, 1)
    last = date_serial(first.year, first.month + 1, 0).day
    return first.replace(day=min(x.day, last))


def week_diff(a, b):
    """DateDiff("ww", a, b): number of Sundays after a up to and including b (negative when b < a)."""
    return (b - EPOCH_SUNDAY).days // 7 - (a - EPOCH_SUNDAY).days // 7


def val(s):
    s = "".join(c for c in s if c not in " \t\n")
    m = re.match(r"[+-]?([0-9]*\.?[0-9]*)([Ee][+-]?[0-9]+)?", s)
    if not m or not re.search(r"[0-9]", m.group(1) or ""):
        return 0
    return float(m.group(0))


def like(s, pat):
    return re.fullmatch("".join(".*" if c == "*" else re.escape(c) for c in pat), s, re.S) is not None


def fmt_amount(txt):
    x = Decimal(txt.strip())
    q = x.quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if q < 0 else "") + f"{abs(int(q)):,}"


def ymd(x):
    return f"{x.year:04d}/{x.month:02d}/{x.day:02d}"


def schedule(rows):
    out = ["請求番号\t請求日\t締め日\t支払予定日\t週\t金額"]
    for row in rows:
        row = (row + [""] * 5)[:5]
        no = row[0]
        parts = row[1].strip(" ").split("/")
        ok = len(parts) == 3 and all(re.fullmatch(r" *[0-9]+ *", p) for p in parts)
        if ok:
            y, m, d = (int(p) for p in parts)
            dt = date_serial(y, m, d)
            ok = (dt.year, dt.month, dt.day) == (y, m, d)
        if not ok:
            out.append(no + "\tERROR 請求日不正")
            continue
        cond = row[3].strip(" ")
        if cond == "末締め翌月末払い":
            closing = date_serial(y, m + 1, 0)
            pay = date_serial(closing.year, closing.month + 2, 0)
        elif like(cond, "末締め翌々月*日払い"):
            closing = date_serial(y, m + 1, 0)
            pay = date_serial(closing.year, closing.month + 2, int(val(cond[6:])))
        elif like(cond, "*日締め翌月*日払い") or like(cond, "*日締め翌月末払い"):
            n = int(val(cond))
            closing = date_serial(y, m, n) if d <= n else date_serial(y, m + 1, n)
            if "翌月末" in cond:
                pay = date_serial(closing.year, closing.month + 2, 0)
            else:
                pay = date_serial(closing.year, closing.month + 1, int(val(cond[cond.index("翌月") + 2:])))
        elif like(cond, "納品後*日"):
            closing = dt
            pay = dt + dtm.timedelta(days=int(val(cond[3:])))
        elif like(cond, "*ヶ月後"):
            closing = dt
            pay = add_months(dt, int(val(cond)))
        else:
            out.append(no + "\tERROR 支払条件不明")
            continue
        if pay.weekday() == 5:
            pay -= dtm.timedelta(days=1)
        elif pay.weekday() == 6:
            pay -= dtm.timedelta(days=2)
        out.append("\t".join([no, ymd(dt), ymd(closing), f"{ymd(pay)} ({WEEKDAY_JA[pay.weekday()]})",
                              str(week_diff(KIJUN, pay)), fmt_amount(row[4])]))
    return "".join(l + "\r\n" for l in out).encode("cp932")
