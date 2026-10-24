"""Hidden check for z_expense_report: runs `python3 -m exp` from another cwd with PYTHONPATH=/work."""
import json, os, shutil, subprocess, sys

CWD = "/tmp/expcwd"
shutil.rmtree(CWD, ignore_errors=True)
os.makedirs(CWD)
fails = []


def ex(*args, db="h.json", env=None):
    e = dict(os.environ, PYTHONPATH="/work")
    e.pop("EXP_DB", None)
    e.update(env or {})
    a = (["--db", db] if db else []) + list(args)
    r = subprocess.run([sys.executable, "-m", "exp", *a], cwd=CWD, capture_output=True, text=True, env=e)
    return r.returncode, r.stdout, r.stderr


def expect(label, got, code=None, out=None, err=None):
    c, o, e = got
    if (code is not None and c != code) or (out is not None and o != out) or (err is not None and e != err):
        fails.append(f"{label}: got exit={c} stdout={o!r} stderr={e[-200:]!r}; want exit={code} stdout={out!r} stderr={err!r}")


def w(name, text):
    with open(os.path.join(CWD, name), "w", encoding="utf-8") as f:
        f.write(text)


w("a.csv", """date,amount,currency,category,note
2026-02-27,1.00,USD,travel,
2026-02-27,1,usd,Travel,
2026-02-28,980,,food,lunch
2026-02-28,980,,food,lunch
2026-02-28,0.5,USD,food,snack
2026-03-01,5000,,food,march
2026-02-14,2.50,EUR,交通費,bus
2026-02-03,"1,200.00",JPY,books,
2026-02-10,301,,zeta,
2026-02-11,301,,alpha,
""")
w("r.json", json.dumps({"base": "JPY", "rates": {"JPY": "1", "USD": "150.5", "EUR": "161"}}))

# --- import idempotency
expect("import a", ex("import", "a.csv"), 0, "imported 10\n")
expect("re-import a", ex("import", "a.csv"), 0, "imported 0, skipped 10\n")
w("b.csv", "date,amount,currency,category,note\n2026-02-28,980,JPY,FOOD,lunch\n2026-02-28,980,,food,lunch\n2026-02-28,980,,food, lunch \n2026-02-20,77,,misc,new\n2026-02-03,1200,,books,\n")
expect("import b (3 lunches vs 2 stored)", ex("import", "b.csv"), 0, "imported 2, skipped 3\n")
expect("add", ex("add", "2026-02-21", "640", "misc", "--note", "x"), 0, "added #13\n")
w("c.csv", "date,amount,currency,category,note\n2026-02-21,640.0,,misc,x\n2026-02-22,1,,misc,\n")
expect("import c (row equal to an added one)", ex("import", "c.csv"), 0, "imported 1, skipped 1\n")
w("bad.csv", "date,amount,currency,category,note\n2026-02-23,5,,misc,\n2026-02-30,5,,misc,\n")
c, o, e = ex("import", "bad.csv")
if c != 1 or not e.startswith("error: "):
    fails.append(f"bad import: exit {c} {e!r}")
with open(os.path.join(CWD, "h.json"), encoding="utf-8") as f:
    n = len(json.load(f)["expenses"])
if n != 14:
    fails.append(f"store should have 14 expenses, has {n}")

# Feb 2026 with r.json: per-expense half-up rounding
# travel: 151 + 151 = 302 (2); food: 980*3 + 75 = 3015 (4); 交通費 2.5*161=402.5 -> 403; books 1200; zeta 301; alpha 301; misc 77+640+1 = 718 (3)
text = "\n".join([
    "Report 2026-02 (by category)",
    f"{'food':<12}{3015:>10,}  (4)",
    f"{'books':<12}{1200:>10,}  (1)",
    f"{'misc':<12}{718:>10,}  (3)",
    f"{'交通費':<12}{403:>10,}  (1)",
    f"{'travel':<12}{302:>10,}  (2)",
    f"{'alpha':<12}{301:>10,}  (1)",
    f"{'zeta':<12}{301:>10,}  (1)",
    "-" * 22,
    f"{'TOTAL':<12}{6240:>10,}  (13)"]) + "\n"
expect("text by category", ex("report", "--month", "2026-02", "--rates", "r.json"), 0, text, "")
expect("csv by category", ex("report", "--month", "2026-02", "--rates", os.path.join(CWD, "r.json"), "--format", "csv"), 0,
       "key,count,total_jpy\nfood,4,3015\nbooks,1,1200\nmisc,3,718\n交通費,1,403\ntravel,2,302\nalpha,1,301\nzeta,1,301\n", "")
c, o, e = ex("report", "--month", "2026-02", "--rates", "r.json", "--format", "json", "--by", "day")
try:
    j = json.loads(o)
    want = {"month": "2026-02", "by": "day", "count": 13, "total_jpy": 6240, "groups": [
        {"key": "2026-02-03", "count": 1, "total_jpy": 1200}, {"key": "2026-02-10", "count": 1, "total_jpy": 301},
        {"key": "2026-02-11", "count": 1, "total_jpy": 301}, {"key": "2026-02-14", "count": 1, "total_jpy": 403},
        {"key": "2026-02-20", "count": 1, "total_jpy": 77}, {"key": "2026-02-21", "count": 1, "total_jpy": 640},
        {"key": "2026-02-22", "count": 1, "total_jpy": 1},
        {"key": "2026-02-27", "count": 2, "total_jpy": 302}, {"key": "2026-02-28", "count": 4, "total_jpy": 3015}]}
    if c != 0 or j != want:
        fails.append(f"json by day: exit {c} {j}")
except ValueError:
    fails.append(f"json by day: not JSON: {o[:200]!r} {e[-200:]!r}")
expect("text by day", ex("report", "--month", "2026-03", "--by", "day", "--rates", "r.json"), 0,
       "Report 2026-03 (by day)\n" + f"{'2026-03-01':<12}{5000:>10,}  (1)\n" + "-" * 22 + "\n" + f"{'TOTAL':<12}{5000:>10,}  (1)\n", "")

# default rates = /work/data/rates.json even though cwd is elsewhere (USD 150.25, EUR 162.4, KRW 0.109)
w("d.csv", "date,amount,currency,category,note\n2026-11-02,3.00,USD,food,\n2026-11-02,0.25,EUR,food,\n2026-11-05,15000,KRW,food,\n2026-11-30,10,USD,fun,\n")
expect("import d", ex("import", "d.csv", db="d.json"), 0, "imported 4\n")
# 450.75->451, 40.6->41, 1635 => food 2127 (3); fun 1502.5 -> 1503
expect("default rates", ex("report", "--month", "2026-11", db="d.json"), 0,
       "Report 2026-11 (by category)\n" + f"{'food':<12}{2127:>10,}  (3)\n" + f"{'fun':<12}{1503:>10,}  (1)\n" + "-" * 22 + "\n" + f"{'TOTAL':<12}{3630:>10,}  (4)\n", "")
expect("EXP_DB", ex("report", "--month", "2026-11", "--format", "csv", db=None, env={"EXP_DB": os.path.join(CWD, "d.json")}), 0,
       "key,count,total_jpy\nfood,3,2127\nfun,1,1503\n", "")

# empty month
expect("empty text", ex("report", "--month", "2025-12"), 0, "no expenses in 2025-12\n", "")
expect("empty csv", ex("report", "--month", "2025-12", "--format", "csv"), 0, "key,count,total_jpy\n", "")
c, o, e = ex("report", "--month", "2025-12", "--format", "json", "--by", "day")
try:
    if c != 0 or json.loads(o) != {"month": "2025-12", "by": "day", "count": 0, "total_jpy": 0, "groups": []}:
        fails.append(f"empty json: {c} {o!r}")
except ValueError:
    fails.append(f"empty json: not JSON {o!r}")
expect("empty store file", ex("report", "--month", "2026-01", db="nothere.json"), 0, "no expenses in 2026-01\n", "")

# errors
for bad in ["2026-13", "2026-2", "202602", "2026-00", "26-02", "2026-02-01", "abcd-ef"]:
    expect(f"invalid month {bad}", ex("report", "--month", bad), 2, "", f"error: invalid month: {bad}\n")
w("x.csv", "date,amount,currency,category,note\n2026-04-01,5,GBP,food,\n2026-05-01,5,USD,food,\n")
expect("import x", ex("import", "x.csv", db="x.json"), 0, "imported 2\n")
expect("no rate", ex("report", "--month", "2026-04", "--rates", "r.json", db="x.json"), 1, "", "error: no rate for GBP\n")
expect("other month fine", ex("report", "--month", "2026-05", "--rates", "r.json", "--format", "csv", db="x.json"), 0,
       "key,count,total_jpy\nfood,1,753\n", "")
c, o, e = ex("report", "--month", "2026-05", "--rates", "missing.json", db="x.json")
if c != 1 or o or not e.startswith("error: "):
    fails.append(f"missing rates file: exit {c} {o!r} {e!r}")

print(f"{len(fails)} failures")
for f in fails[:10]:
    print(" ", f)
sys.exit(1 if fails else 0)
