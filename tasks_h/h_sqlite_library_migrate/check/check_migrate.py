"""Hidden check: biblio.migrate on edge-case v1 databases vs an independent reference migration."""
import hashlib, os, random, re, shutil, sqlite3, subprocess, sys, tempfile
from datetime import datetime, timedelta

TMP = tempfile.mkdtemp()
V1 = """
CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT);
CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER, member TEXT, loaned_at TEXT, returned_at TEXT, fine REAL);
"""
MEMBERS = ["M-0001", "m-0001", " M-0001", "M-0001  ", "m-0002", "M-0010", "a-1", "A-1", " b-77 ", "M-0002", "ｍ-7"]
FINES = [None, None, 0.0, 100.0, 99.99999999, 150.00000001, 49.9999999, 12.3, 299.99999997, 0.0000001]
TITLES = [("吾輩は猫である", "夏目漱石"), ("Dune", None), ("O'Reilly 100% SQL", "x_y"), ("羅生門", "芥川龍之介"), (None, None)]


class Bad(Exception):
    pass


TRE = re.compile(r"[0-9]{4}([-/])[0-9]{2}\1[0-9]{2} [0-9]{2}:[0-9]{2}")


def conv(s):
    if s is None:
        raise Bad("no time")
    t = s.strip(" ")
    if not TRE.fullmatch(t):
        raise Bad(f"bad time {s!r}")
    try:
        dt = datetime.strptime(t.replace("/", "-"), "%Y-%m-%d %H:%M")
    except ValueError:
        raise Bad(f"bad time {s!r}")
    return (dt - timedelta(hours=9)).strftime("%Y-%m-%dT%H:%M:00Z")


def reference(books, loans, version):
    """-> (books, members, loans, stdout) or raises Bad"""
    if version not in (0, 1):
        raise Bad("version")
    bids = {b[0] for b in books}
    codes = set()
    out = []
    for lid, bid, mem, la, ra, fine in loans:
        if mem is None or not mem.strip(" "):
            raise Bad("member")
        if bid is None or bid not in bids:
            raise Bad("book")
        code = "".join(ch.upper() if "a" <= ch <= "z" else ch for ch in mem.strip(" "))
        codes.add(code)
        r = None if ra is None or not ra.strip(" ") else conv(ra)
        out.append((lid, bid, code, conv(la), r, 0 if fine is None else int(round(fine))))
    mid = {c: i for i, c in enumerate(sorted(codes), 1)}
    members = [(i, c) for c, i in sorted(mid.items(), key=lambda x: x[1])]
    lo = sorted((lid, bid, mid[c], la, ra, f) for lid, bid, c, la, ra, f in out)
    return (sorted(books), members, lo, f"migrated to v2: {len(books)} books, {len(members)} members, {len(lo)} loans")


def rand_time(rng):
    special = ["2024-03-01 00:10", "2026-01-01 03:00", "2025-12-31 23:59", "2024-02-29 08:59", "2026-03-01 09:00",
               "2026-05-01 00:00", "2026-07-15 12:34"]
    if rng.random() < 0.4:
        t = rng.choice(special)
    else:
        t = f"{rng.choice([2024, 2025, 2026])}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d} " \
            f"{rng.randint(0, 23):02d}:{rng.randint(0, 59):02d}"
    if rng.random() < 0.35:
        t = t.replace("-", "/")
    if rng.random() < 0.2:
        t = rng.choice([" ", "  "]) + t + rng.choice(["", " "])
    return t


def rand_db(rng, nloans=None):
    ids = sorted(rng.sample(range(1, 30), rng.randint(2, 6)))
    books = [(i, *rng.choice(TITLES)) for i in ids]
    loans = []
    lid = rng.randint(1, 5)
    for _ in range(rng.randint(3, 14) if nloans is None else nloans):
        ra = rng.choice([None, "", "   ", "t", "t", "t"])
        if ra == "t":
            ra = rand_time(rng)
        loans.append((lid, rng.choice(ids), rng.choice(MEMBERS), rand_time(rng), ra, rng.choice(FINES)))
        lid += rng.randint(1, 3)
    return books, loans, rng.choice([0, 1, 1])


def build(path, books, loans, version):
    con = sqlite3.connect(path)
    con.executescript(V1)
    con.execute(f"PRAGMA user_version = {version}")
    con.executemany("INSERT INTO books VALUES (?,?,?)", books)
    con.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?)", loans)
    con.commit()
    con.close()


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(db):
    try:
        r = subprocess.run([sys.executable, "-m", "biblio.migrate", db], cwd="/work", capture_output=True, text=True,
                           timeout=10)
        return r.returncode, r.stdout, r.stderr
    except subprocess.TimeoutExpired:
        return "timeout", "", ""


def read_v2(db):
    con = sqlite3.connect(db)
    try:
        tables = sorted(r[0] for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite%'"))
        ver = con.execute("PRAGMA user_version").fetchone()[0]
        b = con.execute("SELECT id, title, author FROM books ORDER BY id").fetchall()
        m = con.execute("SELECT id, code FROM members ORDER BY id").fetchall()
        lo = con.execute("SELECT id, book_id, member_id, loaned_at, returned_at, fine_yen FROM loans ORDER BY id").fetchall()
        return tables, ver, b, m, lo
    except sqlite3.Error as e:
        return f"error: {e}"
    finally:
        con.close()


def fk_ok(db, books, loans):
    """foreign_key_check empty, deleting a book cascades, deleting a member with loans is refused"""
    p = os.path.join(TMP, "fk.db")
    shutil.copy(db, p)
    con = sqlite3.connect(p)
    try:
        con.execute("PRAGMA foreign_keys = ON")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            return "foreign_key_check reports rows"
        if not loans:
            return None
        bid = loans[0][1]
        before = con.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
        n_b = con.execute("SELECT COUNT(*) FROM loans WHERE book_id = ?", (bid,)).fetchone()[0]
        con.execute("DELETE FROM books WHERE id = ?", (bid,))
        after = con.execute("SELECT COUNT(*) FROM loans").fetchone()[0]
        if after != before - n_b or n_b == 0:
            return f"deleting book {bid} left {after} loans (expected {before - n_b})"
        row = con.execute("SELECT member_id FROM loans LIMIT 1").fetchone()
        if row:
            try:
                con.execute("DELETE FROM members WHERE id = ?", row)
                return "deleting a member with loans was not refused"
            except sqlite3.IntegrityError:
                pass
        return None
    except sqlite3.Error as e:
        return f"error: {e}"
    finally:
        con.close()


def main():
    rng = random.Random(102441)
    sec = {}
    shown = []

    def tally(name, ok, msg):
        st = sec.setdefault(name, [0, 0])
        st[1] += 1
        st[0] += bool(ok)
        if not ok and len(shown) < 10:
            shown.append(f"[{name}] {msg}"[:600])

    cases = [rand_db(rng) for _ in range(22)]
    cases.append(([(1, "x", None)], [], 1))                       # no loans at all
    cases.append(([(5, "a", "b")], [(1, 5, "m-1", "2026-01-01 00:00", "2026/01/01 08:59", 0.49999999)], 0))
    for i, (books, loans, ver) in enumerate(cases):
        db = os.path.join(TMP, f"ok{i}.db")
        build(db, books, loans, ver)
        exp = reference(books, loans, ver)
        rc, out, err = run(db)
        got = read_v2(db)
        expv = (["books", "loans", "members"], 2, exp[0], exp[1], exp[2])
        tally("migrate", got == expv, f"db{i}:\n  expected {expv!r:.250}\n  got      {got!r:.250}\n  stderr {err[-150:]!r}")
        tally("output", rc == 0 and out.strip() == exp[3], f"db{i}: exit {rc}, stdout {out!r:.120} (expected {exp[3]!r})")
        if got == expv:
            tally("foreign_keys", fk_ok(db, books, loans) is None, f"db{i}: {fk_ok(db, books, loans)}")
            h = sha(db)
            rc2, out2, err2 = run(db)
            tally("rerun", rc2 == 0 and out2.strip() == "already at v2" and sha(db) == h,
                  f"db{i} second run: exit {rc2}, stdout {out2!r:.80}, file changed: {sha(db) != h}")
        else:
            tally("foreign_keys", False, f"db{i}: not migrated correctly")
            tally("rerun", False, f"db{i}: not migrated correctly")

    bad_loans = [(None, "member", None), ("   ", "member", None), ("M-1", "book", None), ("M-1", "book", 999),
                 ("M-1", "la", "2026-02-30 10:00"), ("M-1", "la", "2026-03-05 24:00"), ("M-1", "la", "2026-3-05 10:00"),
                 ("M-1", "la", "2026-03-05T10:00"), ("M-1", "la", "2026/03-05 10:00"), ("M-1", "la", ""),
                 ("M-1", "la", None), ("M-1", "ra", "tomorrow"), ("M-1", "ra", "2026-02-29 10:00"),
                 ("M-1", "ra", "2026-03-05 9:30")]
    for j, (mem, kind, val) in enumerate(bad_loans):
        books, loans, ver = rand_db(rng, nloans=rng.randint(4, 9))
        ok_la = "2026-03-05 10:00"
        bid = books[0][0] if kind != "book" else val
        la = val if kind == "la" else ok_la
        ra = val if kind == "ra" else None
        pos = rng.randint(2, len(loans))
        loans.insert(pos, (1000 + j, bid, mem, la, ra, 10.0))
        try:
            reference(books, loans, ver)
            raise SystemExit(f"checker bug: bad case {j} accepted")
        except Bad:
            pass
        db = os.path.join(TMP, f"bad{j}.db")
        build(db, books, loans, ver)
        h = sha(db)
        rc, out, err = run(db)
        tally("failure", rc == 1 and err.strip().startswith("migration failed: ") and sha(db) == h,
              f"bad{j} ({kind}={val!r}, member={mem!r}): exit {rc}, stderr {err.strip()[-120:]!r}, file changed: {sha(db) != h}")
    for v in (3, 7):
        books, loans, _ = rand_db(rng)
        db = os.path.join(TMP, f"ver{v}.db")
        build(db, books, loans, v)
        h = sha(db)
        rc, out, err = run(db)
        tally("failure", rc == 1 and "migration failed: unknown schema version" in err and sha(db) == h,
              f"user_version {v}: exit {rc}, stderr {err.strip()[-120:]!r}, file changed: {sha(db) != h}")

    print("\n".join(shown))
    bad = 0
    for k, (a, t) in sec.items():
        print(f"SECTION {k} {a}/{t}")
        bad += t - a
    sys.exit(1 if bad else 0)


main()
