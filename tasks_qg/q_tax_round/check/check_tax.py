"""Hidden check for q_tax_round: independent reference of docs/SPEC.md, random and edge lines."""
import os, random, subprocess, sys
from fractions import Fraction
sys.path.insert(0, "/work")
from invo.invoice import price_line, summarize


def half_up(fr):
    fr = Fraction(fr)
    n = fr.numerator // fr.denominator
    return n + 1 if fr - n >= Fraction(1, 2) else n


def ref_line(cat, unit, qty, pct):
    gross = unit * qty
    disc = half_up(Fraction(gross) * Fraction(str(pct)) / 100)
    net = gross - disc
    c = cat.strip().lower()
    rate = Fraction(8, 100) if c == "food" else Fraction(0) if c == "exempt" else Fraction(10, 100)
    tax = half_up(net * rate)
    return net, tax, net + tax


cases = [("food", 1450, 1, 7), (" Food ", 999, 3, 2.5), ("EXEMPT", 84, 7, 0), ("Exempt", 1000, 1, 50),
         ("kitchen", 1250, 1, 10), ("FOOD", 125, 1, 0), ("toys", 3333, 3, 33.3), ("food", 2500, 2, 1),
         ("kitchen", 5, 1, 0), ("food", 25, 1, 0), ("stationery", 15, 1, 0), ("food", 1875, 1, 0),
         ("misc", 10, 1, 5), ("misc", 30, 1, 5), ("food", 2, 25, 0)]
rng = random.Random(20261022)
for _ in range(80):
    cases.append((rng.choice(["food", "Food", " FOOD", "exempt", "Exempt ", "kitchen", "toys"]),
                  rng.randrange(1, 5000), rng.randrange(1, 12), rng.choice([0, 0, 5, 7, 10, 12.5, 2.5, 15, 33.3, 50])))
bad, total = [], 0
for cat, unit, qty, pct in cases:
    total += 1
    try:
        got = tuple(price_line("x", cat, unit, qty, pct))
    except Exception as e:
        got = f"error: {type(e).__name__}: {e}"
    want = ref_line(cat, unit, qty, pct)
    if got != want:
        bad.append(f"price_line({cat!r}, {unit}, {qty}, {pct}) = {got}, want {want}")
if bad:
    print(f"{len(bad)} of {len(cases)} lines wrong:"); print("\n".join(bad[:8]))
nlines = len(bad)

total += 1
try:
    lines = [("x%d" % i, *c) for i, c in enumerate(cases)]
    rows, sub, tax, total_ = summarize(lines)
    w = [ref_line(*c) for c in cases]
    assert (sub, tax, total_) == (sum(x[0] for x in w), sum(x[1] for x in w), sum(x[2] for x in w)), "summarize totals"
except Exception as e:
    bad.append(f"summarize: {type(e).__name__}: {e}"); print(bad[-1])

def cli(path):
    r = subprocess.run([sys.executable, "-m", "invo", path], cwd="/work", capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout

import csv
for path in ["/work/data/invoice_0412.csv", "/check/data2/inv.csv"]:
    total += 1
    try:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        exp, s, t = [], 0, 0
        for r in rows:
            n, tx, tot = ref_line(r["category"], int(r["unit_price"]), int(r["qty"]), r["discount_pct"] or "0")
            exp.append(f"{r['item']} {n:,} {tx:,} {tot:,}"); s += n; t += tx
        exp += [f"SUBTOTAL {s:,}", f"TAX {t:,}", f"TOTAL {s + t:,}"]
        got = cli(path).splitlines()
        assert got == exp, f"{path}:\n got {got}\nwant {exp}"
    except Exception as e:
        bad.append(f"{type(e).__name__}: {e}"); print(bad[-1])
if not bad:
    print(f"ok: {len(cases)} lines + 2 invoices")
# graded score (tasks_qg): every case, the totals and each invoice are one item; pass only when all pass, as before
print(f"ITEMS {total - len(bad)}/{total}")
sys.exit(1 if bad else 0)
