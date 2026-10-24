"""Hidden check: tt.repo on edge-case and random databases vs an independent pure-Python reference."""
import os, random, sqlite3, sys, tempfile
from datetime import datetime, timedelta

sys.path.insert(0, "/work")
from tt import repo

SCHEMA = open("/check/orig_schema.sql", encoding="utf-8").read()
TMP = tempfile.mkdtemp()
PNAMES = ["alpha", "Alpha", "beta", "Gamma", "gamma_ray", "Zeta", "delta", "api 50%", "O'Neil", "_infra"]
USERS = ["ann", "Ann", "bob", "a_n", "a%n", "bob "]
TIMES = ["2026-03-01T14:30:00Z", "2026-03-01T15:00:00Z", "2026-03-01T15:00:00Z", "2026-03-01T23:59:00Z",
         "2026-03-02T00:00:00Z", "2026-03-02T04:59:00Z", "2026-03-02T05:00:00Z", "2026-02-28T20:00:00Z",
         "2025-12-31T16:00:00Z", "2026-01-01T03:00:00Z"]
MINUTES = [None, None, 0, 7, 15, 30, 45, 61, 90, 125]
NOTES = [None, None, "", "meeting", "Meeting w/ client", "50% done", "500 done", "a_b test", "axb test", "it's done",
         "back\\slash", "MEETING notes", "naïve"]
SEARCH = ["meeting", "MEET", "%", "_", "50%", "a_b", "'", "it's", "\\", "", "x", "zzz", "' OR 1=1 --"]


def fold(s):
    return "".join(ch.lower() if "A" <= ch <= "Z" else ch for ch in s)


def rand_data(rng):
    pids = sorted(rng.sample(range(1, 40), rng.randint(2, 8)))
    ps = [(i, rng.choice(PNAMES), int(rng.random() < 0.25), rng.choice([None, None, 0, 3000, 4500, 5000, 7777]))
          for i in pids]
    es = []
    eid = rng.randint(1, 4)
    for _ in range(rng.randint(0, 30)):
        es.append((eid, rng.choice(pids[:-1]) if len(pids) > 2 else pids[0], rng.choice(USERS), rng.choice(TIMES),
                   rng.choice(MINUTES), rng.choice(NOTES)))
        eid += rng.randint(1, 3)
    return ps, es   # the last project (when > 2) never has entries


def build(path, ps, es):
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    con.executemany("INSERT INTO projects VALUES (?,?,?,?)", ps)
    con.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?)", es)
    con.commit()
    return con


class Ref:
    def __init__(self, ps, es):
        self.ps, self.es = ps, es
        self.pname = {p[0]: p[1] for p in ps}

    def name_key(self, p):
        return (fold(p[1]), p[0])

    def project_summary(self):
        out = []
        for pid, name, arch, rate in sorted(self.ps, key=self.name_key):
            if arch:
                continue
            mine = [e for e in self.es if e[1] == pid]
            mins = sum(e[4] for e in mine if e[4] is not None)
            out.append({"id": pid, "name": name, "entries": len(mine), "minutes": mins,
                        "amount_yen": None if rate is None else mins * rate // 60})
        return out

    def search_entries(self, text):
        m = [e for e in self.es if e[5] is not None and fold(text) in fold(e[5])]
        return [e[0] for e in sorted(m, key=lambda e: (e[3], e[0]), reverse=True)]

    def all_pages(self, user):
        return [e[0] for e in sorted((e for e in self.es if e[2] == user), key=lambda e: (e[3], e[0]), reverse=True)]

    def daily_minutes(self, user, off):
        d = {}
        for e in self.es:
            if e[2] == user and e[4] is not None:
                day = (datetime.strptime(e[3], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=off)).strftime("%Y-%m-%d")
                d[day] = d.get(day, 0) + e[4]
        return sorted(d.items())

    def running_timers(self):
        return [(e[2], self.pname[e[1]], e[3]) for e in sorted(self.es, key=lambda e: (e[3], e[0])) if e[4] is None]

    def user_report(self, user):
        out = []
        for pid, name, _, _ in sorted(self.ps, key=self.name_key):
            mine = sorted((e for e in self.es if e[1] == pid and e[2] == user), key=lambda e: (e[3], e[0]))
            if mine:
                out.append({"project_id": pid, "project": name, "minutes": sum(e[4] or 0 for e in mine),
                            "entries": [{"id": e[0], "started_at": e[3], "minutes": e[4], "note": e[5]} for e in mine]})
        return out


def typed(v):
    """structure with types made visible, so 583.0 != 583 and Row/tuple/list differences are normalised"""
    if isinstance(v, dict):
        return {k: typed(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [typed(x) for x in v]
    if isinstance(v, sqlite3.Row):
        return [typed(x) for x in v]
    if isinstance(v, bool) or isinstance(v, float):
        return (type(v).__name__, v)
    return v


def walk(con, user, size):
    out, cur = [], None
    for _ in range(100):
        ids, cur = repo.entries_page(con, user, size, cur)
        out += list(ids)
        if cur is None:
            return out
    return out + ["...no end"]


def main():
    rng = random.Random(102442)
    sec, shown = {}, []

    def check(name, label, got, exp):
        ok = typed(got) == typed(exp) if not isinstance(got, str) or not got.startswith("error:") else False
        st = sec.setdefault(name, [0, 0])
        st[1] += 1
        st[0] += ok
        if not ok and len(shown) < 8:
            shown.append(f"{label}:\n  expected {exp!r:.220}\n  got      {got!r:.220}")

    datasets = [rand_data(rng) for _ in range(28)]
    datasets.append(([(1, "solo", 0, 5000)], []))
    datasets.append(([(1, "b", 0, 5000), (2, "A", 0, 7777), (3, "c", 0, None)],
                     [(i, 1 + i % 2, "ann", "2026-03-02T00:00:00Z", 7, None) for i in range(1, 12)]))
    for i, (ps, es) in enumerate(datasets):
        con, ref = build(":memory:", ps, es), Ref(ps, es)

        def safe(f, *a):
            try:
                return f(con, *a)
            except Exception as e:
                return f"error: {type(e).__name__}: {e}"
        check("project_summary", f"db{i} project_summary", safe(repo.project_summary), ref.project_summary())
        for t in SEARCH:
            check("search_entries", f"db{i} search_entries({t!r})", safe(repo.search_entries, t), ref.search_entries(t))
        for u in ["ann", "Ann", "a_n", "bob"]:
            for size in (1, 2, 3, 5):
                try:
                    got = walk(con, u, size)
                except Exception as e:
                    got = f"error: {type(e).__name__}: {e}"
                check("entries_page", f"db{i} pages({u!r}, size={size})", got, ref.all_pages(u))
            for off in (9, 0, -5):
                check("daily_minutes", f"db{i} daily_minutes({u!r}, {off})", safe(repo.daily_minutes, u, off),
                      ref.daily_minutes(u, off))
            stmts = []
            con.set_trace_callback(stmts.append)
            got = safe(repo.user_report, u)
            con.set_trace_callback(None)
            check("user_report", f"db{i} user_report({u!r})", got, ref.user_report(u))
            check("user_report_sql_count", f"db{i} user_report({u!r}) SQL statements", len(stmts) <= 2, True)
        check("running_timers", f"db{i} running_timers", safe(repo.running_timers), ref.running_timers())
        con.close()

        # delete_project on a file DB, with foreign keys off (default) and on, checked from a second connection
        for fk in (0, 1):
            path = os.path.join(TMP, f"del{i}_{fk}.db")
            build(path, ps, es).close()
            pid = rng.choice([p[0] for p in ps] + [999])
            exp_n = sum(1 for e in es if e[1] == pid)
            exp_rows = ([p for p in ps if p[0] != pid], [e for e in es if e[1] != pid])
            c1 = sqlite3.connect(path)
            if fk:
                c1.execute("PRAGMA foreign_keys = ON")
            try:
                n = repo.delete_project(c1, pid)
            except Exception as e:
                n = f"error: {type(e).__name__}: {e}"
            c2 = sqlite3.connect(path, timeout=0.5)
            try:
                rows = (c2.execute("SELECT * FROM projects ORDER BY id").fetchall(),
                        c2.execute("SELECT * FROM entries ORDER BY id").fetchall())
            except sqlite3.Error as e:
                rows = f"error: {e}"
            c2.close()
            c1.close()
            check("delete_project", f"db{i} delete_project({pid}) foreign_keys={fk}", (n, rows), (exp_n, exp_rows))

    print("\n".join(shown))
    bad = 0
    for k, (a, t) in sec.items():
        print(f"SECTION {k} {a}/{t}")
        bad += t - a
    sys.exit(1 if bad else 0)


main()
