"""Hidden check: invoices for new subscriptions vs an independent implementation of docs/FORMAT.md."""
import calendar, os, subprocess, sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

D = "/tmp/bdata"
os.makedirs(D, exist_ok=True)
PLANS = {"basic": 1000, "plus": 3300, "max": 9990, "free": 0}
SUBS = [  # customer, name, plan, start, change_on, change_to
    ("K01", "Mori Yui", "plus", "2026-01-31", "", ""),
    ("K02", "Abe Jun", "basic", "2026-01-30", "", ""),
    ("K03", "Ono Rin", "max", "2026-01-29", "", ""),
    ("K04", "Endo Sho", "plus", "2027-12-31", "", ""),
    ("K05", "Goto Emi", "basic", "2028-01-31", "", ""),
    ("K06", "Hara Taku", "max", "2028-02-29", "", ""),
    ("K07", "Ikeda Nao", "basic", "2026-05-31", "2026-08-15", "max"),
    ("K08", "Kudo Mei", "plus", "2026-01-31", "2026-03-01", "basic"),
    ("K09", "Mura Ken", "max", "2026-03-31", "2026-07-30", "plus"),
    ("K10", "Noda Ai", "basic", "2026-02-10", "2026-04-09", "plus"),
    ("K11", "Oda Riku", "free", "2026-08-31", "2026-12-31", "max"),
    ("K12", "Sano Yu", "plus", "2028-01-31", "2028-02-29", "max"),
]
with open(f"{D}/plans.csv", "w") as f:
    f.write("code,name,monthly\n" + "".join(f"{k},{k.title()},{v}\n" for k, v in PLANS.items()))
with open(f"{D}/subscriptions.csv", "w") as f:
    f.write("customer,name,plan,start,change_on,change_to\n" + "".join(",".join(s) + "\n" for s in SUBS))


def addm(d, n):
    m0 = d.month - 1 + n
    y, m = d.year + m0 // 12, m0 % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def expected(s, on):
    cust, name, plan, start, ch, to = s
    a = date.fromisoformat(start)
    k = 0
    while addm(a, k + 1) <= on:
        k += 1
    ps, pe = addm(a, k), addm(a, k + 1) - timedelta(1)
    pd = (pe - ps).days + 1
    segs = []
    c = date.fromisoformat(ch) if ch else None
    if c is None or c > pe:
        segs = [(plan, ps, pe)]
    elif c <= ps:
        segs = [(to, ps, pe)]
    else:
        segs = [(plan, ps, c - timedelta(1)), (to, c, pe)]
    out = [f"INVOICE {cust} {name}", f"period {ps}..{pe} ({pd} days)"]
    tot = 0
    for p, s0, s1 in segs:
        dd = (s1 - s0).days + 1
        amt = int((Decimal(PLANS[p]) * dd / pd).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        tot += amt
        out.append(f"- {p} {s0}..{s1} {dd}d {amt:,}")
    out.append(f"TOTAL {tot:,} JPY")
    return "\n".join(out), (ps, pe)


sys.path.insert(0, "/work")
os.chdir("/work")
import contextlib, io
from billing.cli import main as billing_main


def call(*args):
    """In-process call of billing.cli.main (same as the command line, but fast)."""
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        try:
            code = billing_main([*args, "--data", D])
        except SystemExit as x:
            code = x.code
    return code or 0, o.getvalue(), e.getvalue()


def run(*args):
    r = subprocess.run([sys.executable, "-m", "billing", *args, "--data", D], capture_output=True, text=True,
                       cwd="/work", env=dict(os.environ, PYTHONPATH="/work"))
    return r.returncode, r.stdout, r.stderr


bad = []
n = 0
for s in SUBS:
    a = date.fromisoformat(s[3])
    for k in range(0, 15):
        for off in (0, 1, 27):
            on = addm(a, k) + timedelta(off)
            exp, _ = expected(s, on)
            n += 1
            code, out, err = call("invoice", "--on", on.isoformat(), s[0])
            if code != 0 or out.rstrip("\n") != exp:
                bad.append((s[0], on.isoformat(), exp, out, err[-200:]))
# periods listing
for s in SUBS[:6]:
    a = date.fromisoformat(s[3])
    exp = []
    for k in range(14):
        ps, pe = addm(a, k), addm(a, k + 1) - timedelta(1)
        exp.append(f"{k:3d} {ps}..{pe} {(pe - ps).days + 1}")
    code, out, err = run("periods", "--count", "14", s[0])
    n += 1
    if code != 0 or out.rstrip("\n") != "\n".join(exp):
        bad.append((s[0], "periods", "\n".join(exp), out, err[-200:]))
# run: all customers active on the date, sorted
on = date(2028, 3, 30)
code, out, _ = run("run", "--on", on.isoformat())
exp = "\n\n".join(expected(s, on)[0] for s in sorted(SUBS) if date.fromisoformat(s[3]) <= on)
n += 1
if code != 0 or out.rstrip("\n") != exp:
    bad.append(("run", on.isoformat(), exp, out, ""))
print(f"{n - len(bad)}/{n} billing scenarios ok")
for b in bad[:3]:
    print("MISMATCH", b[0], b[1], "\n--- expected\n" + b[2] + "\n--- got\n" + b[3] + b[4])
sys.exit(1 if bad else 0)
