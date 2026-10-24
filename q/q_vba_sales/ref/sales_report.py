#!/usr/bin/env python3
"""Port of vba/Module1.bas (月次売上集計).  usage: sales_report.py <売上明細.csv> <yyyymm> <出力ファイル>"""
import csv
import sys
from decimal import Decimal, ROUND_HALF_UP


def cell_num(v):
    v = v.strip()
    return float(v) if v else 0.0          # empty cell = Empty = 0


def clng(x):
    return int(round(x))                   # CLng / Round(x, 0): banker's rounding, like Python's round()


def vba_idiv(a, b):
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def vba_mod(a, b):
    return a - b * vba_idiv(a, b)


def vba_decimal(x):
    return Decimal(format(x, ".15g"))      # Format() works on the 15-digit decimal value of a Double


def fmt_num(x):                            # Format(x, "#,##0"): half away from zero
    d = vba_decimal(x).quantize(Decimal(1), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + "{:,}".format(abs(int(d)))


def fmt_pct(x):                            # Format(x, "0.0%")
    d = (vba_decimal(x) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return ("-" if d < 0 else "") + "{:.1f}%".format(abs(d))


def month_key(v):
    parts = v.strip().split("/")
    return "%04d%02d" % (int(parts[0]), int(parts[1])) if len(parts) == 3 else ""


def main(src, target, dst):
    with open(src, encoding="cp932", newline="") as f:
        rows = list(csv.reader(f))[1:]
    names, cnt, qsum, tot = [], {}, {}, {}
    grand, sum_cnt, sum_qty = 0.0, 0, 0
    for row in rows:
        row = row + [""] * (6 - len(row))
        nm = row[1].strip(" ")             # Trim removes spaces only
        if nm == "" or month_key(row[0]) != target:
            continue
        qty = clng(cell_num(row[3]))
        amt = clng(qty * cell_num(row[4]) * (1 - cell_num(row[5])))
        if nm not in cnt:
            names.append(nm)
            cnt[nm], qsum[nm], tot[nm] = 0, 0, 0.0
        cnt[nm] += 1
        qsum[nm] += qty
        tot[nm] += amt
        grand += amt
        sum_cnt += 1
        sum_qty += qty
    if not names:
        print("対象月のデータがありません")
        return
    idx = list(names)
    n = len(idx)
    for i in range(n - 1):                 # the macro's bubble sort (swaps equal totals too)
        for j in range(n - 1 - i):
            if tot[idx[j]] <= tot[idx[j + 1]]:
                idx[j], idx[j + 1] = idx[j + 1], idx[j]
    lines = ["\t".join(["担当者", "件数", "数量", "ケース", "バラ", "売上", "平均", "構成比"])]
    for k in idx:
        lines.append("\t".join([k, str(cnt[k]), str(qsum[k]), str(vba_idiv(qsum[k], 12)), str(vba_mod(qsum[k], 12)),
                                fmt_num(tot[k]), fmt_num(clng(tot[k] / cnt[k])), fmt_pct(tot[k] / grand)]))
    lines.append("\t".join(["合計", str(sum_cnt), str(sum_qty), str(vba_idiv(sum_qty, 12)), str(vba_mod(sum_qty, 12)),
                            fmt_num(grand), fmt_num(clng(grand / sum_cnt)), "100.0%"]))
    with open(dst, "w", encoding="cp932", newline="") as f:
        f.write("".join(l + "\r\n" for l in lines))


if __name__ == "__main__":
    main(*sys.argv[1:4])
