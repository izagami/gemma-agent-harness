"""Upgrade a library database from schema v1 to v2 (docs/MIGRATION.md). usage: python3 -m biblio.migrate DB"""
import sqlite3
import sys

from biblio.timeconv import jst_to_utc

V2 = """
ALTER TABLE loans RENAME TO loans_v1;
CREATE TABLE members (id INTEGER PRIMARY KEY, code TEXT NOT NULL UNIQUE);
CREATE TABLE loans (id INTEGER PRIMARY KEY,
                    book_id INTEGER NOT NULL REFERENCES books(id),
                    member_id INTEGER NOT NULL REFERENCES members(id),
                    loaned_at TEXT NOT NULL,
                    returned_at TEXT,
                    fine_yen INTEGER NOT NULL);
"""


def migrate(con):
    con.executescript(V2)
    books = {r[0] for r in con.execute("SELECT id FROM books")}
    rows = con.execute("SELECT id, book_id, member, loaned_at, returned_at, fine FROM loans_v1 ORDER BY id").fetchall()
    codes = sorted({(r[2] or "").strip() for r in rows})
    if "" in codes:
        raise ValueError("loan without member")
    member_id = {}
    for i, code in enumerate(codes, 1):
        con.execute("INSERT INTO members VALUES (?, ?)", (i, code))
        member_id[code] = i
    for lid, bid, member, loaned, returned, fine in rows:
        if bid not in books:
            raise ValueError(f"loan {lid}: unknown book {bid}")
        con.execute("INSERT INTO loans VALUES (?,?,?,?,?,?)",
                    (lid, bid, member_id[member.strip()], jst_to_utc(loaned),
                     jst_to_utc(returned) if returned is not None else None, int(fine or 0)))
    con.execute("DROP TABLE loans_v1")
    con.execute("PRAGMA user_version = 2")
    con.commit()
    return len(books), len(codes), len(rows)


def main(argv):
    if len(argv) != 2:
        print("usage: python3 -m biblio.migrate DB", file=sys.stderr)
        return 2
    con = sqlite3.connect(argv[1])
    if con.execute("PRAGMA user_version").fetchone()[0] == 2:
        print("already at v2")
        return 0
    try:
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
