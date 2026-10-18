import ast, glob, importlib, os, random, sys
from datetime import date, timedelta
sys.path.insert(0, "/work")
sys.path.insert(1, "/check")
import orig_ledger as O
import ledger as N

PLACE = {
    "errors": ["LedgerError"],
    "money": ["Money", "parse_money", "format_money", "set_rate", "clear_rates", "convert",
              "set_default_currency", "get_default_currency"],
    "models": ["ACCOUNT_KINDS", "Account", "Posting", "Transaction", "normalize_account_name"],
    "book": ["Ledger"],
    "csvio": ["load_csv", "dump_csv"],
    "reports": ["balance_report", "monthly_report", "trial_balance"],
}
assert os.path.isdir("/work/ledger") and not os.path.exists("/work/ledger.py"), "ledger.py must be gone"
assert sorted(N.__all__) == sorted(O.__all__), N.__all__
for sub, names in PLACE.items():
    mod = importlib.import_module("ledger." + sub)
    for n in names:
        assert getattr(N, n) is getattr(mod, n), (n, sub)
        obj = getattr(mod, n)
        if hasattr(obj, "__module__") and not isinstance(obj, tuple):
            assert obj.__module__ == "ledger." + sub, (n, obj.__module__)

# __init__.py: docstring, imports and __all__ only
tree = ast.parse(open("/work/ledger/__init__.py").read())
for node in tree.body:
    ok = isinstance(node, (ast.Import, ast.ImportFrom)) or \
        (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)) or \
        (isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["__all__"])
    assert ok, "ledger/__init__.py may only contain imports, a docstring and __all__: " + ast.dump(node)[:80]

# each public name is defined exactly once in the package
defs = {}
for f in glob.glob("/work/ledger/**/*.py", recursive=True):
    for node in ast.parse(open(f).read()).body:
        names = []
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names = [node.name]
        elif isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = [node.target.id]
        for n in names:
            defs.setdefault(n, []).append(f)
for n in O.__all__:
    assert len(defs.get(n, [])) == 1, (n, defs.get(n))

# ---- behaviour: differential against the original module
rnd = random.Random(7)

def run(M, ops):
    out = []
    M.clear_rates()
    M.set_default_currency("JPY")
    for op in ops:
        try:
            out.append(op(M))
        except M.LedgerError as e:
            out.append(("ERR", str(e)))
    M.clear_rates()
    M.set_default_currency("JPY")
    return out

def money_text():
    cur = rnd.choice(["JPY", "USD", "EUR", "GBP", "", "XYZ"])
    whole = rnd.randint(0, 2_000_000)
    s = f"{whole:,}" if rnd.random() < 0.5 else str(whole)
    if rnd.random() < 0.5:
        s += "." + str(rnd.randint(0, 99)).zfill(rnd.choice([1, 2, 3]))
    if rnd.random() < 0.3:
        s = "-" + s
    return f"{s} {cur}".strip()

ops = []
for _ in range(300):
    t = money_text()
    ops.append(lambda M, t=t: M.format_money(M.parse_money(t)))
ops.append(lambda M: M.set_rate("USD", "JPY", "151.37"))
ops.append(lambda M: M.set_rate("JPY", "EUR", "0.006133"))
ops.append(lambda M: M.set_rate("GBP", "USD", 0))
for _ in range(200):
    a, b = rnd.choice(["JPY", "USD", "EUR", "GBP"]), rnd.choice(["JPY", "USD", "EUR"])
    v = rnd.randint(-10**7, 10**7)
    ops.append(lambda M, a=a, b=b, v=v: M.format_money(M.convert(M.Money(a, v), b)))
for bad in ["Assets::x", " ", "a:b:c", "income : salary"]:
    ops.append(lambda M, bad=bad: M.normalize_account_name(bad))

ACCTS = ["Assets:Bank", "Assets:Cash", "Liabilities:Card", "Income:Salary", "Expenses:Food",
         "Expenses:Housing:Rent", "Equity:Opening", "Expenses:Fun"]
rows = ["txn,date,description,account,amount"]
for i in range(1, 120):
    d = date(2025, 11, 1) + timedelta(days=rnd.randrange(0, 500))
    cur = rnd.choice(["JPY", "JPY", "USD", "EUR"])
    a, b = rnd.sample(ACCTS, 2)
    v = rnd.randint(1, 500000)
    amt = (f"{v:,}" if cur == "JPY" else f"{v // 100:,}.{v % 100:02d}") + " " + cur
    rows.append(f'{i},{d.isoformat()},"t {i}, x",{a},"{amt}"')
    rows.append(f'{i},{d.isoformat()},"t {i}, x",{b},"-{amt}"')
CSV = "\n".join(rows) + "\n"

def book_ops(M):
    M.set_rate("USD", "JPY", "149.8")
    M.set_rate("EUR", "JPY", "161.25")
    b = M.load_csv(CSV)
    res = [M.dump_csv(b), M.balance_report(b), M.balance_report(b, "USD", date(2026, 3, 1)),
           M.monthly_report(b, "expenses", 2026), M.monthly_report(b, "assets", 2025, "EUR"),
           {k: str(v) for k, v in M.trial_balance(b, "EUR").items()}, str(b.balance("assets")),
           [str(b.balance(a, "USD", date(2026, 1, 1))) for a in ACCTS]]
    M.set_default_currency("USD")
    res += [M.balance_report(b), M.monthly_report(b, "Income", 2026), str(b.balance("Expenses")),
            str(M.parse_money("12.5")), str(M.Money.zero())]
    b.post(date(2026, 1, 1), "p", [("Assets:Bank", "3.25"), ("Income:Salary", "-3.25")])
    res.append(M.dump_csv(b).splitlines()[-1])
    seen = []
    b.on_post(lambda t: seen.append(t.description))
    try:
        b.post(date(2026, 1, 1), "bad", [("Assets:Bank", "1"), ("Income:Salary", "-2")])
    except M.LedgerError as e:
        res.append(str(e))
    b.post(date(2024, 1, 1), "early", [("Assets:Bank", "1"), ("Income:Salary", "-1")])
    res.append((seen, b.transactions[0].description, len(b.transactions)))
    return res
ops.append(book_ops)
for bad_csv in ["txn,date\n1,2\n", "txn,date,description,account,amount\n1,2026-13-01,x,Assets:A,1\n",
                "txn,date,description,account,amount\n1,2026-01-01,x,Foo:A,1\n1,2026-01-01,x,Assets:A,-1\n",
                "txn,date,description,account,amount\n1,2026-01-01,x,Assets:A,1\n1,2026-01-01,x,Income:B,-2\n"]:
    ops.append(lambda M, c=bad_csv: M.dump_csv(M.load_csv(c)))

a, b = run(O, ops), run(N, ops)
for i, (x, y) in enumerate(zip(a, b)):
    assert x == y, (i, x, y)

# shared state set through one module is seen by the others
N.set_default_currency("EUR")
from ledger import money, reports, book, csvio, errors
assert money.get_default_currency() == "EUR" and N.parse_money("1").currency == "EUR"
N.set_rate("USD", "EUR", "0.9"); N.set_rate("JPY", "EUR", "0.006")
assert reports.monthly_report(N.load_csv(CSV), "Assets", 2026).splitlines()[0] == "Assets 2026 (EUR)"
N.clear_rates()
N.set_default_currency("JPY")
money.set_rate("USD", "JPY", "100")
l = book.Ledger(); l.open("Assets:A", "asset"); l.open("Income:B", "income")
l.post(date(2026, 1, 1), "x", [("Assets:A", "2.00 USD"), ("Income:B", "-2.00 USD")])
assert str(l.balance("Assets:A")) == "200 JPY", l.balance("Assets:A")
assert "200 JPY" in N.balance_report(l)
N.clear_rates()
try:
    l.balance("Assets:A")
except errors.LedgerError:
    pass
else:
    raise SystemExit("rates not shared")
try:
    csvio.load_csv("x\n")
except N.LedgerError:
    pass
print("ok")
