"""Hidden check for q_bizdays: library and CLI against an independent model of docs/SPEC.md."""
import datetime as dt, random, subprocess, sys

sys.path.insert(0, "/work")
from bizcal.calendar import Calendar  # noqa: E402
from bizcal.ops import add_business_days, count_business_days  # noqa: E402

HOL = set()
for line in open("/check/orig_holidays.txt", encoding="utf-8"):
    s = line.split("#")[0].split()
    if s:
        HOL.add(dt.date.fromisoformat(s[0]))
ONE = dt.timedelta(days=1)


def biz(d):
    return d.weekday() < 5 and d not in HOL


def exp_add(start, n):
    if n == 0:
        d = start
        while not biz(d):
            d += ONE
        return d
    days = [start + k * ONE * (1 if n > 0 else -1) for k in range(1, 400)]
    return [d for d in days if biz(d)][abs(n) - 1]


def exp_count(a, b):
    return sum(biz(a + k * ONE) for k in range((b - a).days + 1))


fails = cases = 0


def report(ok, what):
    global fails, cases
    cases += 1
    if not ok:
        fails += 1
        if fails <= 8:
            print("FAIL", what)


rng = random.Random(7)
cal = Calendar()
lo = dt.date(2026, 11, 20)
fixed = [(dt.date(2026, 12, 25), 10), (dt.date(2026, 12, 28), 1), (dt.date(2027, 1, 6), -3), (dt.date(2026, 12, 26), 0),
         (dt.date(2026, 12, 29), 0), (dt.date(2026, 12, 28), 0), (dt.date(2027, 1, 12), -6), (dt.date(2026, 5, 3), -1)]
for _ in range(30):
    fixed.append((lo + rng.randint(0, 80) * ONE, rng.randint(-12, 12)))
for start, n in fixed:
    try:
        got = add_business_days(cal, start, n)
    except Exception as e:
        got = repr(e)
    report(got == exp_add(start, n), f"add_business_days({start}, {n}) = {got}, expected {exp_add(start, n)}")
ranges = [(dt.date(2026, 5, 1), dt.date(2026, 5, 8)), (dt.date(2026, 12, 21), dt.date(2027, 1, 8)), (dt.date(2027, 1, 4), dt.date(2027, 1, 4)),
          (dt.date(2027, 1, 6), dt.date(2027, 1, 6))]
for _ in range(14):
    a = lo + rng.randint(0, 70) * ONE
    ranges.append((a, a + rng.randint(0, 40) * ONE))
for a, b in ranges:
    try:
        got = count_business_days(cal, a, b)
    except Exception as e:
        got = repr(e)
    report(got == exp_count(a, b), f"count_business_days({a}, {b}) = {got}, expected {exp_count(a, b)}")
try:
    count_business_days(cal, dt.date(2027, 1, 2), dt.date(2027, 1, 1))
    report(False, "count with first > last did not raise")
except ValueError as e:
    report(str(e) == "first is after last", f"error message {e!r}")
for args, out, code in [(["add", "2026-12-25", "10"], exp_add(dt.date(2026, 12, 25), 10).isoformat(), 0),
                        (["add", "2027-01-08", "-4"], exp_add(dt.date(2027, 1, 8), -4).isoformat(), 0),
                        (["count", "2026-12-28", "2027-01-11"], str(exp_count(dt.date(2026, 12, 28), dt.date(2027, 1, 11))), 0),
                        (["count", "2027-01-11", "2026-12-28"], "", 2)]:
    r = subprocess.run([sys.executable, "-m", "bizcal", *args], capture_output=True, text=True, cwd="/work")
    ok = r.returncode == code and r.stdout.strip() == out and (code == 0 or r.stderr.strip() == "error: first is after last")
    report(ok, f"bizcal {' '.join(args)} -> exit {r.returncode} {r.stdout.strip()!r} {r.stderr.strip()!r}, expected {out!r}")
print(f"{cases - fails}/{cases} cases ok")
print(f"SCORE {cases - fails}/{cases}")
sys.exit(1 if fails else 0)
