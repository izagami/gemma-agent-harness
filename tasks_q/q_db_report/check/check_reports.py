"""Hidden check: run queries/*.sql on many databases (edge cases + random) and compare with a Python reference."""
import calendar, os, random, sqlite3, sys, tempfile

SCHEMA = open("/check/orig_schema.sql", encoding="utf-8").read()
NAMES = ["monthly_category_revenue", "top_customers_by_region", "customers_without_orders", "running_total"]
COLS = {"monthly_category_revenue": ["month", "category", "revenue"],
        "top_customers_by_region": ["region", "rank", "customer", "total"],
        "customers_without_orders": ["id", "name"], "running_total": ["day", "revenue", "running_total"]}


def build(path, d):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO customers VALUES (?,?,?)", d["customers"])
    con.executemany("INSERT INTO categories VALUES (?,?)", d["categories"])
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", d["products"])
    for oid, cid, day, st, items in d["orders"]:
        con.execute("INSERT INTO orders VALUES (?,?,?,?)", (oid, cid, day, st))
        con.executemany("INSERT INTO order_items VALUES (?,?,?,?)", [(oid, p, q, u) for p, q, u in items])
    con.commit(); con.close()


def expected(d):
    cat = {pid: c for pid, _, c, _ in d["products"]}
    catname = dict(d["categories"])
    paid = [o for o in d["orders"] if o[3] == "paid"]
    out = {}
    # monthly
    rows = []
    if paid:
        lo, hi = min(o[2] for o in paid)[:7], max(o[2] for o in paid)[:7]
        y, m = int(lo[:4]), int(lo[5:])
        months = []
        while f"{y:04d}-{m:02d}" <= hi:
            months.append(f"{y:04d}-{m:02d}")
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        rev = {}
        for o in paid:
            for p, q, u in o[4]:
                k = (o[2][:7], cat[p]); rev[k] = rev.get(k, 0) + q * u
        for mo in months:
            for cid, cname in sorted(d["categories"], key=lambda c: c[1]):
                rows.append((mo, cname, rev.get((mo, cid), 0)))
    out["monthly_category_revenue"] = rows
    # top customers
    tot = {}
    for o in paid:
        if o[1] is not None:
            tot[o[1]] = tot.get(o[1], 0) + sum(q * u for _, q, u in o[4])
    cust = {c[0]: c for c in d["customers"]}
    by = {}
    for cid, t in tot.items():
        if t > 0:
            by.setdefault(cust[cid][2] if cust[cid][2] is not None else "(none)", []).append((cust[cid][1], t))
    rows = []
    for reg in sorted(by):
        vals = sorted({t for _, t in by[reg]}, reverse=True)
        rk = {t: i + 1 for i, t in enumerate(vals)}
        for name, t in sorted(by[reg], key=lambda x: (rk[x[1]], x[0])):
            if rk[t] <= 3:
                rows.append((reg, rk[t], name, t))
    out["top_customers_by_region"] = rows
    payers = {o[1] for o in paid}
    out["customers_without_orders"] = [(c[0], c[1]) for c in sorted(d["customers"]) if c[0] not in payers]
    daily = {}
    for o in paid:
        daily[o[2]] = daily.get(o[2], 0) + sum(q * u for _, q, u in o[4])
    run, rows = 0, []
    for day in sorted(daily):
        run += daily[day]; rows.append((day, daily[day], run))
    out["running_total"] = rows
    return out


def rand_data(rng):
    regions = ["kanto", "kansai", "tohoku", None]
    customers = [(i, f"C{i:02d}{rng.choice('abc')}", rng.choice(regions)) for i in range(1, rng.randint(2, 15))]
    categories = [(i, n) for i, n in enumerate(rng.sample(["books", "food", "toys", "garden", "audio", "zakka"], rng.randint(1, 5)), 1)]
    products = [(i, f"p{i}", rng.choice(categories)[0], int(rng.random() < 0.3)) for i in range(1, rng.randint(2, 10))]
    y0, m0 = rng.choice([(2025, 10), (2025, 12), (2026, 1)])
    orders = []
    for oid in range(1, rng.randint(1, 30)):
        mo = m0 - 1 + rng.randint(0, 6); y, m = y0 + mo // 12, mo % 12 + 1
        day = f"{y:04d}-{m:02d}-{rng.randint(1, calendar.monthrange(y, m)[1]):02d}"
        cid = rng.choice([c[0] for c in customers] + [None])
        items = [(rng.choice(products)[0], rng.randint(1, 3), rng.choice([0, 100, 250, 500, 500, 1000])) for _ in range(rng.randint(1, 3))]
        orders.append((oid, cid, day, "cancelled" if rng.random() < 0.25 else "paid", items))
    return {"customers": customers, "categories": categories, "products": products, "orders": orders}


def fixed():
    base = {"customers": [(1, "A", "x"), (2, "B", "x"), (3, "C", "x"), (4, "D", "x"), (5, "E", "x"), (6, "F", None), (7, "G", "y")],
            "categories": [(1, "zz"), (2, "aa"), (3, "never")], "products": [(1, "p", 1, 0), (2, "q", 2, 1)]}
    ties = dict(base, orders=[(1, 1, "2025-11-30", "paid", [(1, 1, 500)]), (2, 2, "2025-11-01", "paid", [(2, 1, 500)]),
                              (3, 3, "2026-02-03", "paid", [(1, 1, 300)]), (4, 4, "2026-02-03", "paid", [(1, 1, 200)]),
                              (5, 5, "2026-02-04", "paid", [(1, 1, 200)]), (6, 6, "2026-02-04", "paid", [(2, 2, 100)]),
                              (7, None, "2026-01-15", "cancelled", [(1, 9, 900)]), (8, 7, "2026-01-15", "cancelled", [(1, 1, 100)]),
                              (9, None, "2026-02-28", "paid", [(2, 1, 1000)])])
    empty = dict(base, orders=[(1, 1, "2026-01-01", "cancelled", [(1, 1, 100)])])
    zero = dict(base, orders=[(1, 1, "2026-03-31", "paid", [(1, 1, 0)]), (2, None, "2026-03-01", "paid", [(2, 2, 50)])])
    return [ties, empty, zero]


def main():
    rng = random.Random(20261022)
    datasets = fixed() + [rand_data(rng) for _ in range(30)]
    sqls = {}
    for n in NAMES:
        p = f"/work/queries/{n}.sql"
        if not os.path.exists(p):
            print(f"missing queries/{n}.sql"); sys.exit(1)
        sqls[n] = open(p, encoding="utf-8").read()
    bad = 0
    tmp = tempfile.mkdtemp()
    for i, d in enumerate(datasets):
        db = os.path.join(tmp, f"{i}.db"); build(db, d)
        exp = expected(d)
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        for n in NAMES:
            try:
                cur = con.execute(sqls[n]); cols = [c[0] for c in cur.description]; got = [tuple(r) for r in cur.fetchall()]
            except Exception as e:
                cols, got = None, f"error: {e}"
            if cols != COLS[n] or got != exp[n]:
                bad += 1
                if bad <= 6:
                    print(f"dataset {i} {n}: columns {cols}\n  expected {exp[n][:8]}\n  got      {got[:8] if isinstance(got, list) else got}")
        con.close()
    total = len(datasets) * len(NAMES)
    print(f"{total - bad}/{total} report checks ok")
    sys.exit(1 if bad else 0)


main()
