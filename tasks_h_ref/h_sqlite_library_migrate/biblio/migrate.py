"""Upgrade a library database from schema v1 to v2 (docs/MIGRATION.md). usage: python3 -m biblio.migrate DB"""
import sqlite3
import sys

from biblio.timeconv import jst_to_utc

V2 = [
    "ALTER TABLE loans RENAME TO loans_v1",
    "CREATE TABLE members (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE)",
    """CREATE TABLE loans (id INTEGER PRIMARY KEY,
                    book_id INTEGER NOT NULL REFERENCES books(id) ON DELETE CASCADE,
                    member_id INTEGER NOT NULL REFERENCES members(id),
                    loaned_at TEXT NOT NULL,
                    returned_at TEXT,
                    fine_yen INTEGER NOT NULL)""",
]


def ascii_upper(s):
    return "".join(ch.upper() if "a" <= ch <= "z" else ch for ch in s)


def convert(con):
    """Validate everything and compute the v2 rows before writing anything."""
    books = {r[0] for r in con.execute("SELECT id FROM books")}
    rows = con.execute("SELECT id, book_id, member, loaned_at, returned_at, fine FROM loans ORDER BY id").fetchall()
    loans = []
    for lid, bid, member, loaned, returned, fine in rows:
        if member is None or not member.strip(" "):
            raise ValueError(f"loan {lid}: no member")
        if bid is None or bid not in books:
            raise ValueError(f"loan {lid}: unknown book {bid}")
        ret = None if returned is None or not returned.strip(" ") else jst_to_utc(returned)
        loans.append((lid, bid, ascii_upper(member.strip(" ")), jst_to_utc(loaned), ret,
                      0 if fine is None else int(round(fine))))
    codes = sorted({l[2] for l in loans})
    member_id = {c: i for i, c in enumerate(codes, 1)}
    return len(books), member_id, [(l[0], l[1], member_id[l[2]], *l[3:]) for l in loans]


def migrate(con):
    con.execute("BEGIN IMMEDIATE")
    try:
        nb, member_id, loans = convert(con)
        for s in V2:
            con.execute(s)
        con.executemany("INSERT INTO members VALUES (?, ?)", [(i, c) for c, i in member_id.items()])
        con.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?)", loans)
        con.execute("DROP TABLE loans_v1")
        con.execute("PRAGMA user_version = 2")
        con.execute("COMMIT")
    except BaseException:
        con.execute("ROLLBACK")
        raise
    return nb, len(member_id), len(loans)


def main(argv):
    if len(argv) != 2:
        print("usage: python3 -m biblio.migrate DB", file=sys.stderr)
        return 2
    con = sqlite3.connect(argv[1], isolation_level=None)
    try:
        ver = con.execute("PRAGMA user_version").fetchone()[0]
        if ver == 2:
            print("already at v2")
            return 0
        if ver not in (0, 1):
            raise ValueError(f"unknown schema version {ver}")
        b, m, n = migrate(con)
    except (ValueError, sqlite3.Error) as e:
        print(f"migration failed: {e}", file=sys.stderr)
        return 1
    finally:
        con.close()
    print(f"migrated to v2: {b} books, {m} members, {n} loans")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
