#!/usr/bin/env python3
"""Hidden check for h_vba_kintai: run /work/kintai.py on the given and on hidden sheets, compare byte for byte with an
independent emulation of the macro (emu_kintai.py)."""
import csv, io, math, os, random, subprocess, sys, tempfile
from fractions import Fraction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_kintai as E

PROG = "/work/kintai.py"
HDR = ["日付", "社員番号", "氏名", "出勤", "退勤", "休憩(分)", "時給"]


def to_csv(rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n")
    w.writerow(HDR); [w.writerow(r) for r in rows]
    return b.getvalue().encode("cp932")


def crafted():
    d = []
    # January: the period starts in December of the previous year (DateSerial(y, 0, 16)); New Year shifts
    d.append(("202601", [["2025/12/15", "123", "佐藤　花子", "9:00", "17:00", "60", "1050"],
                         ["2025/12/16", "123", "佐藤　花子", "9:00", "17:00", "60", "1050"],
                         ["2025/12/27", "387", "高橋 美咲", "21:00", "6:00", "60", "1200"],
                         ["2025/12/31", "387", "高橋 美咲", "22:00", "3:15", "", "1200"],
                         ["2026/1/1", "2041", "鈴木 一郎", "10:00", "19:45", "60", "1100"],
                         ["（年末年始は時給そのまま）", "", "", "", "", "", ""],
                         ["2026/1/3", "123", "佐藤　花子", "9:00", "12:15", "", "1050"],
                         ["2026/1/15", "2041", "鈴木 一郎", "17:00", "22:00", "", "1100"],
                         ["2026/1/16", "2041", "鈴木 一郎", "17:00", "22:00", "", "1100"]]))
    # February period, name with a trailing full-width space at its first row, employee number typed as 0123,
    # breaks typed in different ways, break longer than the shift (skipped), missing clock-out, blank wage on a Sunday
    d.append(("202603", [["2026/2/16", "123", "佐藤　花子　", "9:00", "17:00", "45 ", "1050"],
                         ["2026/2/17", "0123", "佐藤 花子", "9:00", "17:00", "60分", "1050"],
                         ["2026/2/18", "77", " 山口 翼", "9:00", "9:30", "60", "1000"],
                         ["2026/2/19", "77", " 山口 翼", "9:00", "18:07", " 60", "1000"],
                         ["2026/2/22", "77", " 山口 翼", "9:00", "17:30", "", ""],
                         ["2026/2/23", "77", " 山口 翼", "9:00", "", "60", "1000"],
                         ["2026/3/1", "123", "佐藤　花子", "0:00", "8:00", "30", "1050"],
                         ["2026/3/14", "45678", "中村 さくら", "13:00", "22:00", "45分", "1150"],
                         ["2026/3/15", "45678", "中村 さくら", "18:00", "0:00", "", "1150"],
                         ["2026/2/28", "45678", "中村 さくら", "22:15", "8:00", "60", "1150"]]))
    # nothing in the period -> no file
    d.append(("202605", [["2026/4/15", "123", "佐藤　花子", "9:00", "17:00", "60", "1050"],
                         ["2026/5/16", "123", "佐藤　花子", "9:00", "17:00", "60", "1050"],
                         ["2026/5/1", "123", "佐藤　花子", "9:00", "9:10", "", "1050"]]))
    # long day with overtime and night, odd wages (Format rounds .5 up, the monthly total is truncated)
    d.append(("202611", [["2026/10/16", "9", "小林 大輔", "13:00", "23:50", "60", "1015"],
                         ["2026/10/17", "9", "小林 大輔", "13:00", "23:50", "60", "1015"],
                         ["2026/10/20", "31", "加藤 由美", "9:00", "14:45", "30分", "1030"],
                         ["2026/10/21", "9", "小林 大輔", "5:00", "14:00", "60", "1015"],
                         ["2026/10/24", "31", "加藤 由美", "9:00", "14:45", "30分", "1030"],
                         ["", "", "", "", "", "", ""],
                         ["2026/11/3", "31", "加藤 由美", "9:00", "14:45", "30分", "1030"],
                         ["2026/11/15", "9", "小林 大輔", "20:00", "4:59", "", "1015"]]))
    return d


def fragile(rows, target):
    """True when a float sum lands on the other side of an integer than the exact sum (Int() would then depend on
    the summation order, not on the macro's rules) - such sheets are not used."""
    y, m = int(target[:4]), int(target[4:])
    dfrom, dto = E.dateserial(y, m - 1, 16), E.dateserial(y, m, 15)
    acc = {}
    for r in rows:
        if not E.isdate(r[0]) or r[3] == "" or r[4] == "" or E.vtrim(r[1]) == "":
            continue
        d = E.pdate(r[0])
        if d < dfrom or d > dto:
            continue
        sh, sm = E.ptime(r[3]); eh, em = E.ptime(r[4])
        st, en = sh * 60 + sm, eh * 60 + em
        en += 1440 if en <= st else 0
        wk = E.idiv(en - st - E.clng(E.vval(r[5])), 15) * 15
        if wk <= 0:
            continue
        ot = max(wk - 480, 0)
        nt = E.overlap(st, en, 0, 300) + E.overlap(st, en, 1320, 1740)
        w = (1100 if r[6] == "" else int(r[6])) + (100 if d.weekday() >= 5 else 0)
        f = wk * w / 60 + ot * w * 0.25 / 60 + nt * w * 0.25 / 60
        x = Fraction(wk * w, 60) + Fraction(ot * w, 240) + Fraction(nt * w, 240)
        a = acc.setdefault(f"{int(float(r[1])):05d}", [0.0, Fraction(0)])
        a[0] += f; a[1] += x
    return any(math.floor(a[0]) != math.floor(a[1]) for a in acc.values())


def randoms(n):
    rnd = random.Random(20261024)
    staff = [("123", "佐藤　花子", "1050"), ("2041", "鈴木 一郎", "1100"), ("387", "高橋 美咲", "1200"),
             ("5", "田中 健", ""), ("77", "山口 翼　", "1000"), ("45678", "中村 さくら", "1150"), ("9", "小林 大輔", "1015")]
    out = []
    while len(out) < n:
        y, m = 2026, rnd.randint(1, 12)
        dfrom = E.dateserial(y, m - 1, 16)
        rows = []
        for _ in range(rnd.randint(8, 30)):
            no, nm, w = rnd.choice(staff)
            day = dfrom + __import__("datetime").timedelta(days=rnd.randint(-3, 33))
            sh = rnd.choice([5, 8, 9, 9, 10, 13, 17, 18, 21, 22, 23])
            smin = rnd.choice([0, 0, 0, 5, 15, 30, 50])
            dur = rnd.randint(120, 660)
            e = (sh * 60 + smin + dur) % 1440
            brk = rnd.choice(["", "0", "45", "60", "60", "30分", "60分", " 45"])
            end = "" if rnd.random() < 0.04 else f"{e // 60}:{e % 60:02d}"
            rows.append([f"{day.year}/{day.month}/{day.day}", no, nm, f"{sh}:{smin:02d}", end, brk, w])
            if rnd.random() < 0.05:
                rows.append(["", "", "", "", "", "", ""])
        target = f"{y}{m:02d}"
        if not fragile(rows, target) and E.report(rows, target) is not None:
            out.append((target, rows))
    return out


def main():
    fails, sc, cnt = [], [0, 0], [0]
    tmp = tempfile.mkdtemp()

    def grade(want, got):
        if want is None:
            sc[1] += 1
            sc[0] += got is None
            return
        wl, gl = want.split(b"\r\n"), (got or b"").split(b"\r\n")
        bad = [j for j in range(len(wl)) if j >= len(gl) or wl[j] != gl[j]]
        sc[0] += (len(wl) - len(bad)) if (got == want or bad) else 0
        sc[1] += len(wl)

    def run(src, target, want, name):
        cnt[0] += 1
        dst = os.path.join(tmp, f"out_{cnt[0]}.txt")
        r = subprocess.run([sys.executable, PROG, src, target, dst], capture_output=True, text=True, timeout=20)
        got = open(dst, "rb").read() if os.path.exists(dst) else None
        grade(want, got)
        if got != want:
            fails.append((name, want, got, r.stderr))

    run("/work/data/kintai.csv", "202604", open("/check/orig_expected_kyuyo_202604.txt", "rb").read(), "given data 202604")
    for i, (target, rows) in enumerate(crafted() + randoms(6)):
        assert not fragile(rows, target)
        src = os.path.join(tmp, f"in{i}.csv")
        open(src, "wb").write(to_csv(rows))
        run(src, target, E.report(rows, target), f"hidden sheet {i} ({target})")
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
