"""Independent emulation of vba/Module1.bas (勤怠集計) with VBA semantics, used by the hidden check.

rows: list of [date, empno, name, in, out, break, wage] strings (sheet 勤怠 without header), target: "yyyymm".
Returns the file as bytes exactly as `Print #` writes it (cp932, CRLF), or None when the macro writes no file."""
import datetime, math, re
from decimal import Decimal, ROUND_HALF_UP
from fractions import Fraction

YOUBI = "月火水木金土日"            # Format(d, "aaa") on a Japanese Windows


def vtrim(s):
    return s.strip(" ")


def clng(x):
    f = Fraction(x)
    fl = f.numerator // f.denominator
    rem = f - fl
    if rem > Fraction(1, 2) or (rem == Fraction(1, 2) and fl % 2 == 1):
        fl += 1
    return fl


def vval(s):
    """Val(): skips blanks/tabs, reads the longest leading number, stops at the first other character."""
    t = s.replace(" ", "").replace("\t", "")
    m = re.match(r"[+-]?(\d+\.?\d*|\.\d+)([eEdD][+-]?\d+)?", t)
    if not m:
        return 0.0
    return float(m.group(0).replace("d", "e").replace("D", "e"))


def idiv(a, b):
    q = abs(a) // abs(b)
    return q if (a >= 0) == (b > 0) else -q


def vmod(a, b):
    return a - b * idiv(a, b)


def fmt_int(x):                    # Format(x, "#,##0"): half away from zero
    d = Decimal(f"{x:.15g}").quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + f"{abs(int(d)):,}"


def hm(mins):
    return f"{idiv(mins, 60)}:{vmod(mins, 60):02d}"


def isdate(s):
    try:
        pdate(s)
        return True
    except (ValueError, TypeError):
        return False


def pdate(s):
    p = s.strip().split("/")
    if len(p) != 3:
        raise ValueError(s)
    return datetime.date(int(p[0]), int(p[1]), int(p[2]))


def ptime(s):                      # "h:mm" -> (hour, minute)
    h, m = s.strip().split(":")
    return int(h), int(m)


def dateserial(y, m, d):
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return datetime.date(y, m, 1) + datetime.timedelta(days=d - 1)


def overlap(a1, a2, b1, b2):
    s, t = max(a1, b1), min(a2, b2)
    return t - s if t > s else 0


def report(rows, target):
    y, m = int(target[:4]), int(target[4:])
    dfrom, dto = dateserial(y, m - 1, 16), dateserial(y, m, 15)
    emps = {}                      # key -> name, first appearance order
    recs = []
    for r in rows:
        r = (list(r) + [""] * 7)[:7]
        if not isdate(r[0]):
            continue
        d = pdate(r[0])
        if d < dfrom or d > dto:
            continue
        if vtrim(r[1]) == "":
            continue
        if r[3] == "" or r[4] == "":
            continue
        sh, sm = ptime(r[3]); eh, em = ptime(r[4])
        st, en = sh * 60 + sm, eh * 60 + em
        if en <= st:
            en += 1440
        brk = clng(vval(r[5]))
        wk = idiv(en - st - brk, 15) * 15
        if wk <= 0:
            continue
        ot = wk - 480 if wk > 480 else 0
        nt = overlap(st, en, 0, 300) + overlap(st, en, 1320, 1740)
        w = 1100 if r[6] == "" else clng(float(r[6]))
        if d.weekday() >= 5:
            w += 100
        pay = wk * w / 60 + ot * w * 0.25 / 60 + nt * w * 0.25 / 60
        key = f"{clng(float(r[1])):05d}"
        if key not in emps:
            emps[key] = vtrim(r[2])
        recs.append((key, d, (sh, sm), (eh, em), brk, wk, ot, nt, pay))
    if not emps:
        return None
    out = ["集計期間\t" + dfrom.strftime("%Y/%m/%d") + "\t" + dto.strftime("%Y/%m/%d"),
           "\t".join(["社員番号", "氏名", "日付", "出勤", "退勤", "休憩", "実働", "残業", "深夜", "日額"])]
    grand = 0
    for key, name in emps.items():
        days = swk = sot = snt = 0
        tot = 0.0
        for k, d, s, e, brk, wk, ot, nt, pay in recs:
            if k != key:
                continue
            out.append("\t".join([key, name, f"{d.month}/{d.day}({YOUBI[d.weekday()]})", f"{s[0]}:{s[1]:02d}",
                                  f"{e[0]}:{e[1]:02d}", str(brk), hm(wk), hm(ot), hm(nt), fmt_int(pay)]))
            days += 1; swk += wk; sot += ot; snt += nt
            tot += pay
        out.append("\t".join([key, name, "計", f"{days}日", "", "", hm(swk), hm(sot), hm(snt), fmt_int(math.floor(tot))]))
        grand += math.floor(tot)
    out.append("\t".join(["合計", f"{len(emps)}名"] + [""] * 7 + [fmt_int(grand)]))
    return "".join(l + "\r\n" for l in out).encode("cp932")
