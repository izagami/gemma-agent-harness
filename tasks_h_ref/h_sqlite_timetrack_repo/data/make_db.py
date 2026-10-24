"""Sample time-tracking database. make_db.build(path) -> open connection (path may be ':memory:')."""
import os, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = [(1, "Alpha", 0, 6000), (2, "Beta", 0, None), (3, "Old site", 1, 3000)]
ENTRIES = [(1, 1, "ann", "2026-03-02T01:00:00Z", 60, "kickoff meeting"),
           (2, 1, "bob", "2026-03-02T05:00:00Z", 30, "review"),
           (3, 2, "ann", "2026-03-03T02:00:00Z", 45, None),
           (4, 1, "ann", "2026-03-04T03:00:00Z", None, "coding"),
           (5, 3, "bob", "2026-02-01T00:00:00Z", 15, "old task")]


def build(path, projects=PROJECTS, entries=ENTRIES):
    con = sqlite3.connect(path)
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    con.executemany("INSERT INTO projects VALUES (?,?,?,?)", projects)
    con.executemany("INSERT INTO entries VALUES (?,?,?,?,?,?)", entries)
    con.commit()
    return con
