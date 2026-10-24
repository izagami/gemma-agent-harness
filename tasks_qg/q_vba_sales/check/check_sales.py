#!/usr/bin/env python3
"""Hidden check for q_vba_sales: run /work/sales_report.py on the given and on hidden sheets, compare byte for byte
with an independent emulation of the macro (emu_sales.py)."""
import csv, io, os, random, subprocess, sys, tempfile
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_sales as E

PROG = "/work/sales_report.py"
HDR = ["日付", "担当者", "商品", "数量", "単価", "値引率"]
ITEMS = ["ボールペン", "コピー用紙 A4", "ファイル", "トナー", "付箋", "クリップ", "マーカー"]


def to_csv(rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n")
    w.writerow(HDR); [w.writerow(r) for r in rows]
    return b.getvalue().encode("cp932")


def crafted():
    d = []
    # full-width spaces are not removed by Trim; ASCII spaces are
    d.append(("202604", [["2026/4/1", "伊藤", "付箋", "10", "98", "0"], ["2026/4/2", "伊藤　", "付箋", "5", "98", "0"],
                         ["2026/4/2", "  伊藤", "付箋", "1", "98", ""], ["2026/4/3", "　伊藤", "付箋", "2", "100", ""],
                         ["2026/4/4", "佐藤", "トナー", "1", "8800", "0.1"]]))
    # returns: negative quantities and totals -> \ and Mod truncate toward zero, negative formats
    d.append(("202605", [["2026/5/1", "高橋", "ファイル", "5", "120", ""], ["2026/5/2", "高橋", "ファイル", "-30", "120", ""],
                         ["2026/5/2", "鈴木", "トナー", "2", "8800", "0"], ["2026/5/9", "田中", "付箋", "-7", "98", "0"],
                         ["2026/5/9", "田中", "付箋", "-6", "98", "0"], ["2026/5/9", "中村", "クリップ", "25", "35", ""]]))
    # exact ties in the percentage (grand total 16000): Format rounds half away from zero
    d.append(("202606", [["2026/6/1", "A社担当", "トナー", "1", "1000", ""], ["2026/6/1", "B社担当", "トナー", "1", "5000", ""],
                         ["2026/6/2", "C社担当", "トナー", "1", "3000", ""], ["2026/6/2", "D社担当", "トナー", "1", "7000", ""]]))
    # CLng / Round ties (banker's) and equal totals (order of ties)
    d.append(("202607", [["2026/7/1", "山本", "ファイル", "5", "61", "0.5"], ["2026/7/1", "小林", "ファイル", "7", "61", "0.5"],
                         ["2026/7/2", "加藤", "付箋", "1", "1", "0.5"], ["2026/7/2", "加藤", "付箋", "3", "1", "0.5"],
                         ["2026/7/3", "吉田", "付箋", "5", "1", "0.5"], ["2026/7/3", "山田", "マーカー", "-5", "61", "0.5"],
                         ["2026/7/4", "佐々木", "ファイル", "2", "76", ""], ["2026/7/4", "山口", "ファイル", "1", "152", ""],
                         ["2026/7/5", "松本", "ファイル", "4", "38", ""]]))
    # decimals in prices, other years and zero-padded dates, rows without a name
    d.append(("202604", [["2025/4/1", "井上", "トナー", "3", "8800", ""], ["2026/04/05", "井上", "付箋", "3", "98.5", ""],
                         ["2026/4/30", "木村", "付箋", "11", "98.5", "0.15"], ["2026/4/30", "", "付箋", "3", "98", ""],
                         ["2027/4/1", "木村", "トナー", "9", "8800", ""], ["2026/4/15", "林", "コピー用紙 A4", "13", "449.5", "0.02"]]))
    return d


def ok_data(rows, target):
    """Skip random sheets whose result would depend on details outside the macro's normal behaviour."""
    acc, grand = {}, 0
    for r in rows:
        nm = E.vtrim(r[1])
        if not nm or E.yyyymm(r[0]) != target:
            continue
        q = E.clng(E.vnum(r[3])); a = E.clng(q * E.vnum(r[4]) * (1 - E.vnum(r[5])))
        v = acc.setdefault(nm, [0, 0]); v[0] += 1; v[1] += a; grand += a
    if not acc or grand <= 0:
        return False
    for c, t in acc.values():
        x = Fraction(t / grand) * 1000
        fr = x - (x.numerator // x.denominator)
        if fr != Fraction(1, 2) and abs(fr - Fraction(1, 2)) < Fraction(1, 10 ** 6):
            return False
        if -0.0005 < t / grand < 0 or -0.5 < t / c < 0:
            return False
    return True


def randoms(n):
    rnd = random.Random(20261022)
    names = ["佐藤", "鈴木", "高橋", "田中", "伊藤", "渡辺", "山本", "中村", "小林", "加藤", "伊藤　", " 佐藤"]
    out = []
    while len(out) < n:
        target = "2026%02d" % rnd.randint(1, 12)
        rows = []
        for _ in range(rnd.randint(8, 30)):
            m = int(target[4:]) if rnd.random() < 0.85 else rnd.randint(1, 12)
            day = rnd.randint(1, 28)
            qty = rnd.choice([rnd.randint(1, 40), rnd.randint(1, 40), -rnd.randint(1, 30)])
            price = rnd.choice(["61", "98", "98.5", "120", "150", "450", "8800", "35", "101", "449.5"])
            rate = rnd.choice(["", "0", "0.05", "0.1", "0.15", "0.2", "0.25", "0.5"])
            rows.append([f"2026/{m}/{day}", rnd.choice(names), rnd.choice(ITEMS), str(qty), price, rate])
        if ok_data(rows, target):
            out.append((target, rows))
    return out


def main():
    fails, cases = [], 0
    sc = [0, 0]

    def grade(want, got):
        # graded: lines in their place; bytes differing with no differing line (line ends, encoding) = all wrong
        wl, gl = want.split(b"\r\n"), got.split(b"\r\n")
        bad = [j for j in range(len(wl)) if j >= len(gl) or wl[j] != gl[j]]
        sc[0] += (len(wl) - len(bad)) if (got == want or bad) else 0
        sc[1] += len(wl)
    tmp = tempfile.mkdtemp()
    # 1. the given sheet must reproduce the given output
    given = "/work/data/uriage_meisai.csv"
    r = subprocess.run([sys.executable, PROG, given, "202604", os.path.join(tmp, "g.txt")], capture_output=True, text=True, timeout=30)
    got = open(os.path.join(tmp, "g.txt"), "rb").read() if os.path.exists(os.path.join(tmp, "g.txt")) else b""
    want = open("/check/orig_expected_report_202604.txt", "rb").read()
    cases += 1
    grade(want, got)
    if got != want:
        fails.append(("given data", want, got, r.stderr))
    # 2. hidden sheets
    for i, (target, rows) in enumerate(crafted() + randoms(8)):
        src, dst = os.path.join(tmp, f"in{i}.csv"), os.path.join(tmp, f"out{i}.txt")
        open(src, "wb").write(to_csv(rows))
        want = E.report(rows, target)
        r = subprocess.run([sys.executable, PROG, src, target, dst], capture_output=True, text=True, timeout=30)
        got = open(dst, "rb").read() if os.path.exists(dst) else b""
        wl, gl = want.split(b"\r\n"), got.split(b"\r\n")
        cases += len(wl) - 1
        grade(want, got)
        if got != want:
            fails.append((f"hidden sheet {i} ({target})", want, got, r.stderr))
    for name, want, got, err in fails[:4]:
        wl, gl = want.decode("cp932").split("\r\n"), got.decode("cp932", "replace").split("\r\n")
        diff = next((j for j in range(max(len(wl), len(gl))) if (wl[j:j + 1] or [None]) != (gl[j:j + 1] or [None])), None)
        print(f"MISMATCH {name}: line {diff}: expected {wl[diff:diff + 1]!r} got {gl[diff:diff + 1]!r}"
              + (f" (crlf/encoding: expected {want[:60]!r} got {got[:60]!r})" if diff is None else "") + (f" stderr: {err[-300:]}" if err else ""))
    print(f"{cases} lines compared, {len(fails)} sheet(s) differ")
    print(f"SCORE {sc[0]}/{sc[1]}")
    sys.exit(1 if fails else 0)


main()
