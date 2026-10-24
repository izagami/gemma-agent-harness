"""Hidden check: shop.repo on edge-case and random databases vs an independent pure-Python reference."""
import random, sqlite3, sys

sys.path.insert(0, "/work")
from shop import repo

SCHEMA = open("/check/orig_schema.sql", encoding="utf-8").read()
NAMES = ["Aoki", "O'Brien", "Baba", "x%y", "a_b", "Chiba", "Doi", "Ab\\c", "aoki", "Endo"]
PNAMES = ["pen", "Pencil", "50% off", "100%", "a_b", "axb", "ink", "INK jet", "o'clock", "back\\slash", "bag"]


def build(d):
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA)
    for t, rows in d.items():
        con.executemany(f"INSERT INTO {t} VALUES ({','.join('?' * len(rows[0]))})", rows) if rows else None
    con.commit()
    return con


def rand_data(rng):
    cs = [(i, rng.choice(NAMES), None) for i in range(1, rng.randint(2, 12))]
    addrs, aid = [], 1
    for c in cs:
        k = rng.randint(0, 3); prim = rng.randint(-1, k - 1)
        for j in range(k):
            addrs.append((aid, c[0], rng.choice(["Tokyo", "Osaka", "Sendai", "Naha"]), int(j == prim))); aid += 1
    ps = [(i, rng.choice(PNAMES), rng.choice([100, 100, 250, 250, 250, 900])) for i in range(1, rng.randint(2, 14))]
    os_ = [(i, rng.choice(cs)[0], f"2026-0{rng.randint(1, 6)}-1{rng.randint(0, 9)}") for i in range(1, rng.randint(1, 16))]
    its = [(rng.choice(os_)[0], rng.choice(ps)[0], rng.randint(1, 4)) for _ in range(rng.randint(0, 20) if os_ else 0)]
    return {"customers": cs, "addresses": addrs, "products": ps, "orders": os_, "order_items": its}


class Ref:
    def __init__(self, d):
        self.d = d
        self.city = {}
        for _, cid, city, prim in d["addresses"]:
            if prim:
                self.city[cid] = city

    def list_customers(self):
        return [{"id": c[0], "name": c[1], "city": self.city.get(c[0])} for c in sorted(self.d["customers"], key=lambda c: (c[1], c[0]))]

    def find_customer(self, name):
        m = [c for c in self.list_customers() if c["name"] == name]
        return min(m, key=lambda c: c["id"]) if m else None

    def order_counts_since(self, day):
        cnt = {c[0]: 0 for c in self.d["customers"]}
        for _, cid, at in self.d["orders"]:
            if at >= day:
                cnt[cid] += 1
        rows = sorted(((c[1], cnt[c[0]], c[0]) for c in self.d["customers"]), key=lambda r: (-r[1], r[0], r[2]))
        return [(n, k) for n, k, _ in rows]

    def search_products(self, text):
        fold = lambda s: "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in s)
        return [p[1] for p in sorted(self.d["products"], key=lambda p: (p[1], p[0])) if fold(text) in fold(p[1])]

    def all_pages(self):
        return [p[1] for p in sorted(self.d["products"], key=lambda p: (-p[2], p[0]))]

    def orders_with_items(self, cid):
        prod = {p[0]: p for p in self.d["products"]}
        out = []
        for oid, c, at in sorted(self.d["orders"], key=lambda o: (o[2], o[0])):
            if c != cid:
                continue
            its = sorted(((prod[p][1], q, prod[p][2], p) for o, p, q in self.d["order_items"] if o == oid), key=lambda x: (x[0], x[3]))
            items = [(n, q, pr) for n, q, pr, _ in its]
            out.append({"id": oid, "ordered_at": at, "items": items, "total": sum(q * pr for _, q, pr in items)})
        return out


def walk(con, size):
    out, cur = [], None
    for _ in range(200):
        names, cur = repo.products_page(con, size, cur)
        out += names
        if cur is None:
            return out
    return out + ["...no end"]


def main():
    rng = random.Random(10221)
    datasets = [rand_data(rng) for _ in range(30)]
    bad, total, shown = 0, 0, []

    def check(label, got, exp):
        nonlocal bad, total
        total += 1
        if got != exp:
            bad += 1
            if len(shown) < 8:
                shown.append(f"{label}:\n  expected {exp!r:.300}\n  got      {got!r:.300}")
    for i, d in enumerate(datasets):
        con, ref = build(d), Ref(d)
        def safe(f, *a):
            try:
                return f(con, *a)
            except Exception as e:
                return f"error: {type(e).__name__}: {e}"
        check(f"db{i} list_customers", safe(repo.list_customers), ref.list_customers())
        for n in rng.sample(NAMES, 3) + ["nobody"]:
            check(f"db{i} find_customer({n!r})", safe(repo.find_customer, n), ref.find_customer(n))
        day = f"2026-0{rng.randint(1, 6)}-15"
        got = safe(repo.order_counts_since, day)
        check(f"db{i} order_counts_since({day})", got if isinstance(got, str) else [tuple(r) for r in got], ref.order_counts_since(day))
        for t in ["%", "_", "0%", "a_b", "'", "\\", "in", "PEN", ""]:
            check(f"db{i} search_products({t!r})", safe(repo.search_products, t), ref.search_products(t))
        for size in (1, 2, 3, 5):
            try:
                got = walk(con, size)
            except Exception as e:
                got = f"error: {e}"
            check(f"db{i} products pages size={size}", got, ref.all_pages())
        for cid in {o[1] for o in d["orders"]} | {d["customers"][0][0]}:
            stmts = []
            con.set_trace_callback(stmts.append)
            got = safe(repo.orders_with_items, cid)
            con.set_trace_callback(None)
            if not isinstance(got, str):
                got = [dict(o, items=[tuple(x) for x in o["items"]]) for o in got]
            check(f"db{i} orders_with_items({cid})", got, ref.orders_with_items(cid))
            total += 1
            if len(stmts) > 2:
                bad += 1
                if len(shown) < 8:
                    shown.append(f"db{i} orders_with_items({cid}) ran {len(stmts)} SQL statements (at most 2 allowed)")
        con.close()
    print("\n".join(shown))
    print(f"{total - bad}/{total} repo checks ok")
    sys.exit(1 if bad else 0)


main()
