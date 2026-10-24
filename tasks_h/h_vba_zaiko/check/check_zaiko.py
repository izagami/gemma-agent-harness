#!/usr/bin/env python3
"""Hidden check for h_vba_zaiko: run /work/zaiko_hyoka.py on the given and on hidden sheets, compare byte for byte with
an independent emulation of the macro (emu_zaiko.py)."""
import csv, io, os, random, subprocess, sys, tempfile
from decimal import Decimal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_zaiko as E

PROG = "/work/zaiko_hyoka.py"
TH = ["日付", "品番", "区分", "数量", "単価"]
MH = ["品番", "品名", "入数"]


def to_csv(hdr, rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n")
    w.writerow(hdr); [w.writerow(r) for r in rows]
    return b.getvalue().encode("cp932")


def read_csv(path):
    rows = list(csv.reader(io.StringIO(open(path, "rb").read().decode("cp932"))))
    return rows[1:]


MASTER = [["A-1001", "クリアファイル A4 10枚入", "12"], ["A-1002", "フラットファイル 青", "24"],
          ["A-1003", "ボックスファイル", "10"], ["A-1004", "リングファイル 2穴", "6"], ["B-2001", "ゼムクリップ 小", "100"],
          ["B-2002", "ダブルクリップ 中", "10"], ["C-3001", "トナー TN-27J", "1"], ["C-3002", "トナー TN-27J 互換", "1"],
          ["D-4001", "輪ゴム #16 箱", ""], ["F-6001", "パンチ 2穴", "6"], ["a-1001", "重複登録 (使わない)", "99"]]


def crafted(given_t, given_m):
    d = []
    # the given sheets at earlier cut-off dates (rows after the date are ignored, but still validated)
    d.append((given_t, given_m, "2026/04/08"))
    d.append((given_t, given_m, "2026/04/21"))
    # 区分 with an ASCII space is fine (Trim); a full-width space is an input error -> no file at all
    d.append(([["2026/5/1", "A-1001", "入庫", "24", "85"], ["2026/5/2", "A-1001", "出庫 ", "5", ""],
               ["2026/5/2", " a-1001", " 入庫", "12", "86"]], MASTER, "2026/05/31"))
    d.append(([["2026/5/1", "A-1001", "入庫", "24", "85"], ["2026/5/2", "A-1001", "入庫　", "5", "85"]], MASTER, "2026/05/31"))
    # a bad 区分 after the cut-off date still stops the macro
    d.append(([["2026/5/1", "B-2001", "入庫", "100", "12.5"], ["2026/6/3", "B-2001", "返品", "5", ""]], MASTER, "2026/05/31"))
    # nothing left in stock -> no file
    d.append(([["2026/5/1", "B-2001", "入庫", "100", "12.5"], ["2026/5/9", "B-2001", "出庫", "100", ""],
               ["2026/5/9", "C-3001", "調整", "2", ""]], MASTER, "2026/05/31"))
    # negative stock (\ and Mod truncate toward zero), full-width space in a code (Trim keeps it -> another item),
    # master entries with lower case codes, blank rows, codes missing from the master
    d.append(([["2026/6/1", "A-1001", "入庫", "10", "88"], ["2026/6/2", "A-1001", "出庫", "24", ""],
               ["2026/6/2", "A-1001", "調整", "-1", ""], ["", "", "", "", ""], ["2026/6/3", "A-1001　", "入庫", "36", "90"],
               ["2026/6/3", "a-1003", "入庫", "13", "99.5"], ["2026/6/4", "A-1003", "出庫", "4", ""],
               ["2026/6/5", "C-3002", "入庫", "1", "1980"], ["2026/6/5", "C-3002", "調整", "-3", ""],
               ["2026/6/6", "Z-9999", "入庫", "7", "15"], ["2026/6/7", "B-2002", "入庫", "25", "36.5"],
               ["", "B-2002", "出庫", "10", ""], ["2026/6/8", "B-2002", "調整", "-27", ""]], MASTER, "2026/06/30"))
    # CLng half-to-even, Format half-up on exact .xx5 / .x5% values, equal amounts in the selection sort
    d.append(([["2026/7/1", "D-4001", "入庫", "3", "0.5"], ["2026/7/1", "A-1004", "入庫", "8", "12.6"],
               ["2026/7/1", "B-2001", "入庫", "5", "12.5"], ["2026/7/1", "B-2002", "入庫", "40", "2.7"],
               ["2026/7/2", "A-1002", "入庫", "8", "13"], ["2026/7/2", "A-1003", "入庫", "1", "62"],
               ["2026/7/2", "C-3001", "入庫", "1", "104"], ["2026/7/3", "F-6001", "入庫", "1", "62"],
               ["2026/7/3", "A-1001", "入庫", "200", "0.5"], ["2026/7/3", "C-3002", "入庫", "1", "104"],
               ["2026/7/4", "A-1001", "出庫", "3", ""], ["2026/7/4", "B-2002", "出庫", "15", ""]], MASTER, "2026/07/31"))
    return d


def ambiguous(trans, master, kijun):
    """Skip random sheets that would overflow a Long in the macro (amounts and quantities here are small rationals, so
    Format never sees a value that is only nearly a .5 tie)."""
    try:
        E.report(trans, master, kijun)
    except OverflowError:
        return True
    return False


def randoms(n):
    rnd = random.Random(20261024)
    codes = ["A-1001", "A-1002", "A-1003", "A-1004", "B-2001", "B-2002", "C-3001", "C-3002", "D-4001", "F-6001",
             "G-7001", "a-1002", " B-2001", "C-3001 "]
    prices = ["85", "88", "240", "12.5", "99.9", "1980", "1.5", "36.5", "0.5", "350", "62", "13.3"]
    out = []
    while len(out) < n:
        m = rnd.randint(1, 12)
        rows, stock = [], {}
        for _ in range(rnd.randint(10, 35)):
            mm = m if rnd.random() < 0.85 else rnd.randint(1, 12)
            c = rnd.choice(codes)
            k = rnd.choice(["入庫", "入庫", "出庫", "出庫", "調整"])
            if k == "入庫":
                rows.append([f"2026/{mm}/{rnd.randint(1, 28)}", c, k, str(rnd.choice([1, 3, 5, 8, 12, 24, 40, 100, 7])),
                             rnd.choice(prices)])
            elif k == "出庫":
                rows.append([f"2026/{mm}/{rnd.randint(1, 28)}", c, k, str(rnd.randint(1, 15)), ""])
            else:
                rows.append([f"2026/{mm}/{rnd.randint(1, 28)}", c, k, str(rnd.randint(-5, 3)), ""])
            if rnd.random() < 0.05:
                rows.append(["", "", "", "", ""])
        kijun = f"2026/{m:02d}/28"
        if not ambiguous(rows, MASTER, kijun) and E.report(rows, MASTER, kijun) is not None:
            out.append((rows, MASTER, kijun))
    return out


def main():
    fails, sc, cnt = [], [0, 0], [0]
    tmp = tempfile.mkdtemp()

    def grade(want, got):
        if want is None:              # the macro writes no file
            sc[1] += 1
            sc[0] += got is None
            return
        wl, gl = want.split(b"\r\n"), (got or b"").split(b"\r\n")
        bad = [j for j in range(len(wl)) if j >= len(gl) or wl[j] != gl[j]]
        sc[0] += (len(wl) - len(bad)) if (got == want or bad) else 0
        sc[1] += len(wl)

    def run(tpath, mpath, kijun, want, name):
        cnt[0] += 1
        dst = os.path.join(tmp, f"out_{cnt[0]}.txt")
        if os.path.exists(dst):
            os.remove(dst)
        r = subprocess.run([sys.executable, PROG, tpath, mpath, kijun, dst], capture_output=True, text=True, timeout=20)
        got = open(dst, "rb").read() if os.path.exists(dst) else None
        grade(want, got)
        if got != want:
            fails.append((name, want, got, r.stderr))

    gt, gm = "/work/data/nyushukko.csv", "/work/data/hinmoku.csv"
    run(gt, gm, "2026/04/30", open("/check/orig_expected_zaiko_20260430.txt", "rb").read(), "given data 2026/04/30")
    given_t, given_m = read_csv("/check/orig_nyushukko.csv"), read_csv("/check/orig_hinmoku.csv")
    for i, (t, m, kijun) in enumerate(crafted(given_t, given_m) + randoms(8)):
        tp, mp = os.path.join(tmp, f"t{i}.csv"), os.path.join(tmp, f"m{i}.csv")
        open(tp, "wb").write(to_csv(TH, t)); open(mp, "wb").write(to_csv(MH, m))
        run(tp, mp, kijun, E.report(t, m, kijun), f"hidden sheet {i} ({kijun})")
    for name, want, got, err in fails[:4]:
        if want is None or got is None:
            print(f"MISMATCH {name}: expected {'no file' if want is None else 'a file'}, got "
                  f"{'no file' if got is None else 'a file'}" + (f" stderr: {err[-300:]}" if err else ""))
            continue
        wl, gl = want.decode("cp932").split("\r\n"), got.decode("cp932", "replace").split("\r\n")
        diff = next((j for j in range(max(len(wl), len(gl))) if (wl[j:j + 1] or [None]) != (gl[j:j + 1] or [None])), None)
        print(f"MISMATCH {name}: line {diff}: expected {repr(wl[diff:diff + 1])[:300]} got {repr(gl[diff:diff + 1])[:300]}"
              + (f" (crlf/encoding: expected {want[:60]!r} got {got[:60]!r})" if diff is None else "")
              + (f" stderr: {err[-300:]}" if err else ""))
    print(f"{len(fails)} case(s) differ")
    print(f"SCORE {sc[0]}/{sc[1]}")
    sys.exit(1 if fails else 0)


main()
