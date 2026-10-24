#!/usr/bin/env python3
"""Hidden check for q_vba_dates: run /work/pay_schedule.py on the given and on hidden sheets, compare byte for byte
with an independent emulation of the macro (emu_dates.py)."""
import csv, io, os, random, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import emu_dates as E

PROG = "/work/pay_schedule.py"
HDR = ["請求番号", "請求日", "取引先", "支払条件", "金額"]

CRAFTED = [
    ["H-001", "2026/2/10", "A", "31日締め翌月10日払い", "1000"],      # DateSerial(2026, 2, 31) rolls over to 3/3
    ["H-002", "2026/2/28", "A", "30日締め翌月末払い", "2000"],
    ["H-003", "2024/2/29", "A", "1ヶ月後", "3000"],                    # leap day
    ["H-004", "2026/1/31", "A", "13ヶ月後", "4000"],
    ["H-005", "2026/3/31", "A", "1ヶ月後", "5000"],
    ["H-006", "2026/11/30", "A", "末締め翌々月10日払い", "6000"],       # into the next year
    ["H-007", "2026/12/25", "A", "20日締め翌月10日払い", "7000"],       # closing in January of the next year
    ["H-008", "2026/1/5", "A", "末日締め翌月25日払い", "8000"],          # Val("末日...") = 0 -> end of month
    ["H-009", "2026/3/1", "A", "納品後0日", "9000"],                    # a Sunday
    ["H-010", "2026/3/28", "A", "納品後1日", "10000"],                  # before the base date: negative weeks
    ["H-011", "2026/4/4", "A", "納品後1日", "1500.5"],                  # Format rounds half away from zero
    ["H-012", "2026/4/4", "A", "納品後0日", "2500.5"],
    ["H-013", "2026/04/01", "A", "末締め翌月末払い", "98765.4"],
    ["H-014", " 2026/5/20 ", "A", " 20日締め翌月10日払い ", "100"],
    ["H-015", "2026/5/21", "A", "20日締め翌月10日払い", "100"],
    ["H-016", "2026/13/1", "A", "末締め翌月末払い", "100"],
    ["H-017", "2026/0/10", "A", "末締め翌月末払い", "100"],
    ["H-018", "2026-04-01", "A", "末締め翌月末払い", "100"],
    ["H-019", "R8/4/1", "A", "末締め翌月末払い", "100"],
    ["H-020", "2026/4", "A", "末締め翌月末払い", "100"],
    ["H-021", "2026/6/31", "A", "末締め翌月末払い", "100"],
    ["H-022", "2026/9/15", "A", "翌月末払い", "100"],
    ["H-023", "2026/9/15", "A", "末締め翌々月5日払い", "123456"],
    ["H-024", "2026/10/31", "A", "2ヶ月後", "100"],
    ["H-025", "2026/8/16", "A", "納品後45日", "100"],
    ["H-026", "2027/2/15", "A", "10日締め翌月31日払い", "100"],         # pay day 31 in March: fine; in other months rolls over
    ["H-027", "2026/3/15", "A", "10日締め翌月31日払い", "100"],
    ["H-028", "2025/12/31", "A", "末締め翌月末払い", "100"],
    ["H-029", "2026/7/4", "A", "5日締め翌月末払い", "100"],
    ["H-030", "2026/7/6", "A", "5日締め翌月末払い", "100"],
]


def to_csv(rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n")
    w.writerow(HDR); [w.writerow(r) for r in rows]
    return b.getvalue().encode("cp932")


def randoms(n):
    rnd = random.Random(2610)
    conds = ["末締め翌月末払い", "末締め翌々月10日払い", "末締め翌々月20日払い", "20日締め翌月10日払い", "25日締め翌月末払い",
             "15日締め翌月15日払い", "31日締め翌月5日払い", "納品後30日", "納品後60日", "1ヶ月後", "2ヶ月後", "6ヶ月後", "現金"]
    rows = []
    for i in range(n):
        y, m, d = rnd.choice([2025, 2026, 2026, 2027]), rnd.randint(1, 12), rnd.choice([1, 5, 10, 15, 20, 25, 28, 29, 30, 31])
        amt = rnd.choice([str(rnd.randint(1, 3000) * 100), f"{rnd.randint(1, 9999)}.5", str(rnd.randint(1, 99))])
        rows.append([f"R-{i:03d}", f"{y}/{m}/{d}", "B", rnd.choice(conds), amt])
    return rows


def main():
    fails, cases = [], 0
    sc = [0, 0]
    tmp = tempfile.mkdtemp()
    for name, rows in [("given", None), ("hidden-1", CRAFTED), ("hidden-2", randoms(60))]:
        src = "/work/data/seikyu.csv" if rows is None else os.path.join(tmp, name + ".csv")
        if rows is not None:
            open(src, "wb").write(to_csv(rows))
        want = open("/check/orig_expected_pay_schedule.txt", "rb").read() if rows is None else E.schedule(rows)
        dst = os.path.join(tmp, name + ".txt")
        r = subprocess.run([sys.executable, PROG, src, dst], capture_output=True, text=True, timeout=30)
        got = open(dst, "rb").read() if os.path.exists(dst) else b""
        wl, gl = want.split(b"\r\n"), got.split(b"\r\n")
        cases += len(wl) - 2
        bad = [j for j in range(len(wl)) if j >= len(gl) or wl[j] != gl[j]]
        # graded: lines in their place; a sheet whose bytes differ with no differing line (line ends, encoding,
        # trailing extra lines) counts as all wrong
        sc[0] += (len(wl) - len(bad)) if (got == want or bad) else 0
        sc[1] += len(wl)
        if got != want:
            fails.append(name)
            for j in bad[:3]:
                print(f"MISMATCH {name} line {j}: expected {wl[j].decode('cp932')!r} got "
                      f"{gl[j].decode('cp932', 'replace') if j < len(gl) else None!r}")
            if not bad:
                print(f"MISMATCH {name}: line endings or encoding differ: expected {want[:40]!r} got {got[:40]!r}")
            if r.stderr:
                print("stderr:", r.stderr[-300:])
            print(f"  {name}: {len(bad)} of {len(wl) - 1} lines differ")
    print(f"{cases} rows compared, {len(fails)} sheet(s) differ")
    print(f"SCORE {sc[0]}/{sc[1]}")
    sys.exit(1 if fails else 0)


main()
