"""Hidden check: migrate many v1 databases (edge cases, random, failing) and compare with an independent reference."""
import os, random, re, sqlite3, subprocess, sys, tempfile

TMP = tempfile.mkdtemp()


def make_v1(path, contacts, notes):
    con = sqlite3.connect(path)
    con.executescript("CREATE TABLE contacts (id INTEGER PRIMARY KEY, full_name TEXT, email TEXT, tags TEXT);"
                      "CREATE TABLE notes (id INTEGER PRIMARY KEY, contact_id INTEGER, body TEXT); PRAGMA user_version = 1;")
    con.executemany("INSERT INTO contacts VALUES (?,?,?,?)", contacts)
    con.executemany("INSERT INTO notes VALUES (?,?,?)", notes)
    con.commit(); con.close()


def dump(path):
    con = sqlite3.connect(path)
    out = {"version": con.execute("PRAGMA user_version").fetchone()[0],
           "tables": sorted(r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))}
    for t in out["tables"]:
        out[t] = sorted(con.execute(f"SELECT * FROM {t}").fetchall(), key=repr)
    con.close()
    return out


def expected(contacts, notes):
    """None if the migration must fail."""
    ws = " 　\t"
    rows, tagnames, links = [], [], set()
    for cid, full, email, tags in contacts:
        if full is None or not full.strip(ws):
            return None
        s = full.strip(ws)
        i = min([s.find(c) for c in " 　" if c in s] or [-1])
        last, first = (s, "") if i < 0 else (s[:i], s[i + 1:].strip(ws))
        rows.append((cid, last, first, email))
        for t in (tags or "").split(","):
            t = t.strip().lower()
            if t:
                if t not in tagnames:
                    tagnames.append(t)
                links.add((cid, t))
    ids = {c[0] for c in contacts}
    good = [n for n in notes if n[1] in ids]
    orphan = [n for n in notes if n[1] not in ids]
    return {"contacts": sorted(rows), "tags": sorted(tagnames), "links": sorted(links), "notes": sorted(good), "orphan": sorted(orphan)}


def run(db):
    return subprocess.run([sys.executable, "-m", "crm.migrate", db], cwd="/work", capture_output=True, text=True, timeout=30)


def compare(i, contacts, notes, log):
    db = os.path.join(TMP, f"{i}.db")
    make_v1(db, contacts, notes)
    before = dump(db)
    exp = expected(contacts, notes)
    r = run(db)
    if exp is None:
        if r.returncode != 1 or not r.stderr.startswith("migration failed: "):
            return log(i, f"must fail with status 1 and 'migration failed: ...', got {r.returncode} {r.stdout!r} {r.stderr[-200:]!r}")
        if dump(db) != before:
            return log(i, "failed migration changed the database (must stay exactly v1)")
        return True
    if r.returncode != 0:
        return log(i, f"exit {r.returncode}: {r.stderr[-300:]}")
    msg = f"migrated to v2: {len(exp['contacts'])} contacts, {len(exp['tags'])} tags, {len(exp['notes'])} notes, {len(exp['orphan'])} orphan notes"
    if r.stdout.strip() != msg:
        return log(i, f"output {r.stdout.strip()!r} != {msg!r}")
    con = sqlite3.connect(db)
    try:
        tables = sorted(x[0] for x in con.execute("SELECT name FROM sqlite_master WHERE type='table'"))
        if tables != ["contact_tags", "contacts", "notes", "orphan_notes", "tags"]:
            return log(i, f"tables {tables}")
        if con.execute("PRAGMA user_version").fetchone()[0] != 2:
            return log(i, "user_version is not 2")
        got = sorted(con.execute("SELECT id, last_name, first_name, email FROM contacts").fetchall())
        if got != exp["contacts"]:
            return log(i, f"contacts {got[:4]} != {exp['contacts'][:4]}")
        tags = sorted(x[0] for x in con.execute("SELECT name FROM tags"))
        if tags != exp["tags"]:
            return log(i, f"tags {tags} != {exp['tags']}")
        links = sorted(con.execute("SELECT ct.contact_id, t.name FROM contact_tags ct JOIN tags t ON t.id = ct.tag_id").fetchall())
        if links != exp["links"]:
            return log(i, f"contact_tags {links[:6]} != {exp['links'][:6]}")
        if sorted(con.execute("SELECT * FROM notes").fetchall()) != exp["notes"]:
            return log(i, "notes differ")
        if sorted(con.execute("SELECT * FROM orphan_notes").fetchall(), key=repr) != sorted(exp["orphan"], key=repr):
            return log(i, "orphan_notes differ")
        if con.execute("PRAGMA foreign_key_check").fetchall():
            return log(i, "foreign_key_check reports problems")
        # cascade: deleting a contact removes its notes and tag links
        if exp["contacts"]:
            cid = exp["contacts"][0][0]
            con.execute("PRAGMA foreign_keys = ON")
            con.execute("DELETE FROM contacts WHERE id = ?", (cid,))
            left = con.execute("SELECT (SELECT COUNT(*) FROM notes WHERE contact_id = ?) + (SELECT COUNT(*) FROM contact_tags WHERE contact_id = ?)", (cid, cid)).fetchone()[0]
            con.rollback()
            if left:
                return log(i, "deleting a contact does not delete its notes/contact_tags (ON DELETE CASCADE)")
    finally:
        con.close()
    after = dump(db)
    r2 = run(db)
    if r2.returncode != 0 or r2.stdout.strip() != "already at v2" or dump(db) != after:
        return log(i, f"second run must print 'already at v2' and change nothing: {r2.returncode} {r2.stdout!r} {r2.stderr[-200:]!r}")
    return True


def main():
    rng = random.Random(1022)
    cases = [
        ([(1, "  山田　太郎 ", "t@x", " VIP, tokyo ,vip,,"), (2, "Suzuki Hanako Maria", None, "Tokyo"), (3, "Prince", "p@x", ",")],
         [(1, 1, "a"), (2, None, "b"), (3, 99, "c"), (4, 3, "d")]),
        ([(1, "A B", None, None)], []),
        ([(1, "Ok Name", None, "a"), (2, "   ", None, "b")], [(1, 1, "x")]),          # blank name -> fail
        ([(1, "Ok Name", None, "a"), (2, None, None, "b")], []),                    # NULL name -> fail
        ([(5, "佐藤　花子", "s@x", "営業,営業 , 東京")], [(7, 5, "メモ")]),
        ([], [(1, 1, "orphan only")]),
    ]
    words = ["Abe", "Ito", "山田", "Kato", "佐藤", "Mori"]
    for _ in range(20):
        contacts = []
        for cid in rng.sample(range(1, 60), rng.randint(0, 8)):
            sep = rng.choice([" ", "　", "  ", " 　"])
            parts = rng.sample(words, rng.randint(1, 3))
            name = rng.choice(["", " ", "　"]) + sep.join(parts) + rng.choice(["", " "])
            tags = rng.choice([None, "", ",".join(rng.choice([" a", "B ", "b", "", "c", "Ａ"]) for _ in range(rng.randint(1, 4)))])
            contacts.append((cid, name, rng.choice([None, f"{cid}@x"]), tags))
        if rng.random() < 0.15 and contacts:
            c = contacts[0]; contacts[0] = (c[0], rng.choice([None, " 　 "]), c[2], c[3])
        ids = [c[0] for c in contacts] + [None, 999]
        notes = [(nid, rng.choice(ids), f"n{nid}") for nid in range(1, rng.randint(1, 10))]
        cases.append((contacts, notes))
    ok, total, shown = 0, len(cases), []

    def log(i, msg):
        if len(shown) < 6:
            shown.append(f"case {i}: {msg}")
        return False
    for i, (c, n) in enumerate(cases):
        ok += bool(compare(i, c, n, log))
    print("\n".join(shown))
    print(f"{ok}/{total} migration cases ok")
    sys.exit(0 if ok == total else 1)


main()
