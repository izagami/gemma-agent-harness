"""Hidden check for q_duration: parse/format/CLI against an independent model of docs/SPEC.md."""
import random, subprocess, sys
from decimal import Decimal

sys.path.insert(0, "/work")
from durfmt import format_duration, parse_duration  # noqa: E402

SZ = {"d": 86400, "h": 3600, "m": 60, "s": 1}
fails = cases = 0


def report(ok, what):
    global fails, cases
    cases += 1
    if not ok:
        fails += 1
        if fails <= 8:
            print("FAIL", what)


def exp_format(n):
    out = ""
    for u in "dhms":
        q, n = divmod(n, SZ[u])
        if q:
            out += f"{q}{u}"
    return out or "0s"


def run(f, arg):
    try:
        return ("ok", f(arg))
    except ValueError as e:
        return ("err", str(e))
    except Exception as e:
        return ("crash", repr(e))


PARSE = [
    ("1h30m", ("ok", 5400)), ("1h 30m", ("ok", 5400)), (" 1 h 30 m ", ("ok", 5400)), ("\t2d\t4h", ("ok", 187200)),
    ("2 d", ("ok", 172800)), ("90s", ("ok", 90)), ("1.5h", ("ok", 5400)), ("0.5m", ("ok", 30)), ("0.1h", ("ok", 360)),
    ("0.29h", ("ok", 1044)), ("1.25d 0.5h", ("ok", 109800)), ("0.001d", ("err", "not a whole number of seconds")),
    ("1.5s", ("err", "not a whole number of seconds")), ("0.7m", ("ok", 42)), ("1d1h1m1s", ("ok", 90061)),
    ("30m1h", ("err", "unit out of order: h")), ("1h1h", ("err", "unit out of order: h")),
    ("1s 1m", ("err", "unit out of order: m")), ("1d 2h 3h", ("err", "unit out of order: h")),
    ("", ("err", "empty duration")), ("   ", ("err", "empty duration")), ("1H", ("err", "invalid duration: '1H'")),
    ("-1h", ("err", "invalid duration: '-1h'")), ("1h30", ("err", "invalid duration: '1h30'")),
    ("1.h", ("err", "invalid duration: '1.h'")), (".5h", ("err", "invalid duration: '.5h'")), ("h", ("err", "invalid duration: 'h'")),
    ("1e2s", ("err", "invalid duration: '1e2s'")), ("1h,30m", ("err", "invalid duration: '1h,30m'")), ("0s", ("ok", 0)),
]
for text, exp in PARSE:
    got = run(parse_duration, text)
    report(got == exp, f"parse_duration({text!r}) -> {got}, expected {exp}")
rng = random.Random(11)
for n in [0, 1, 59, 60, 3600, 86400, 86460, 90000, 3601, 7322] + [rng.randint(0, 10 ** 7) for _ in range(20)]:
    got = run(format_duration, n)
    report(got == ("ok", exp_format(n)), f"format_duration({n}) -> {got}, expected {exp_format(n)!r}")
    if got[0] == "ok":
        back = run(parse_duration, got[1])
        report(back == ("ok", n), f"round trip {n} -> {got[1]!r} -> {back}")
report(run(format_duration, -5) == ("err", "negative duration"), "format_duration(-5)")
for _ in range(15):  # random spacing and fractions, exact decimal arithmetic
    units = sorted(rng.sample("dhms", rng.randint(1, 4)), key="dhms".index)
    text, total = "", Decimal(0)
    for u in units:
        num = str(rng.randint(0, 30)) if rng.random() < 0.6 else f"{rng.randint(0, 9)}.{rng.choice(['5', '25', '75', '1', '05'])}"
        total += Decimal(num) * SZ[u]
        text += rng.choice(["", " ", "  "]) + num + rng.choice(["", " ", "\t"]) + u
    text += rng.choice(["", " "])
    exp = ("ok", int(total)) if total == int(total) else ("err", "not a whole number of seconds")
    got = run(parse_duration, text)
    report(got == exp, f"parse_duration({text!r}) -> {got}, expected {exp}")
for args, out, err, code in [(["parse", " 1 h 30 m "], "5400", "", 0), (["format", "3600"], "1h", "", 0),
                             (["format", "0"], "0s", "", 0), (["parse", "30m1h"], "", "error: unit out of order: h", 2)]:
    r = subprocess.run([sys.executable, "-m", "durfmt", *args], capture_output=True, text=True, cwd="/work")
    report((r.returncode, r.stdout.strip(), r.stderr.strip()) == (code, out, err),
           f"durfmt {args} -> {(r.returncode, r.stdout.strip(), r.stderr.strip())}, expected {(code, out, err)}")
print(f"{cases - fails}/{cases} cases ok")
print(f"SCORE {cases - fails}/{cases}")
sys.exit(1 if fails else 0)
