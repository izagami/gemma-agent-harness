"""Upgrade a contacts database from schema v1 to v2 (docs/MIGRATION.md)."""
import sqlite3
import sys

from crm.names import split_name, split_tags

V2 = """
CREATE TABLE contacts_v2 (id INTEGER PRIMARY KEY, last_name TEXT NOT NULL, first_name TEXT NOT NULL, email TEXT);
CREATE TABLE tags (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE);
CREATE TABLE contact_tags (contact_id INTEGER NOT NULL REFERENCES contacts(id),
                           tag_id INTEGER NOT NULL REFERENCES tags(id),
                           PRIMARY KEY (contact_id, tag_id));
CREATE TABLE notes_v2 (id INTEGER PRIMARY KEY, contact_id INTEGER NOT NULL REFERENCES contacts(id), body TEXT);
CREATE TABLE orphan_notes (id INTEGER PRIMARY KEY, contact_id INTEGER, body TEXT);
"""


def tag_id(con, name):
    row = con.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
    if row:
        return row[0]
    return con.execute("INSERT INTO tags(name) VALUES (?)", (name,)).lastrowid


def migrate(con):
    con.executescript(V2)
    for cid, full, email, tags in con.execute("SELECT id, full_name, email, tags FROM contacts").fetchall():
        last, first = split_name(full)
        con.execute("INSERT INTO contacts_v2 VALUES (?,?,?,?)", (cid, last, first, email))
        for t in split_tags(tags):
            con.execute("INSERT INTO contact_tags VALUES (?,?)", (cid, tag_id(con, t)))
        con.commit()
    con.execute("INSERT INTO notes_v2 SELECT id, contact_id, body FROM notes")
    con.executescript("""
        DROP TABLE notes; ALTER TABLE notes_v2 RENAME TO notes;
        DROP TABLE contacts; ALTER TABLE contacts_v2 RENAME TO contacts;
        PRAGMA user_version = 2;
    """)
    n = lambda t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    return n("contacts"), n("tags"), n("notes"), n("orphan_notes")


def main(argv):
    if len(argv) != 1:
        print("usage: python3 -m crm.migrate DB", file=sys.stderr)
        return 2
    con = sqlite3.connect(argv[0])
    try:
        c, t, n, o = migrate(con)
    except Exception as e:
        print(f"migration failed: {e}", file=sys.stderr)
        return 1
    finally:
        con.close()
    print(f"migrated to v2: {c} contacts, {t} tags, {n} notes, {o} orphan notes")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
