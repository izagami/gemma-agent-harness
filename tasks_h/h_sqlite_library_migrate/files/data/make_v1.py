"""Create a sample v1 library database: python3 data/make_v1.py PATH"""
import sqlite3, sys

BOOKS = [(1, "吾輩は猫である", "夏目漱石"), (2, "Dune", "Frank Herbert"), (3, "羅生門", "芥川龍之介")]
LOANS = [(1, 1, "M-0001", "2026-03-02 14:10", "2026-03-09 16:00", None),
         (2, 2, "M-0002", "2026-03-05 11:00", None, None),
         (3, 1, "M-0002", "2026-03-10 15:30", "2026-03-30 12:00", 300.0),
         (4, 3, "M-0003", "2026-03-12 13:45", "2026-03-19 17:20", 0.0)]


def build(path, books=BOOKS, loans=LOANS, version=1):
    con = sqlite3.connect(path)
    con.executescript("""
        CREATE TABLE books (id INTEGER PRIMARY KEY, title TEXT, author TEXT);
        CREATE TABLE loans (id INTEGER PRIMARY KEY, book_id INTEGER, member TEXT, loaned_at TEXT, returned_at TEXT,
                            fine REAL);""")
    con.execute(f"PRAGMA user_version = {int(version)}")
    con.executemany("INSERT INTO books VALUES (?,?,?)", books)
    con.executemany("INSERT INTO loans VALUES (?,?,?,?,?,?)", loans)
    con.commit()
    con.close()


if __name__ == "__main__":
    build(sys.argv[1])
