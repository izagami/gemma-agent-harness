"""Sample database: python3 data/make_db.py PATH"""
import os, sqlite3, sys

HERE = os.path.dirname(os.path.abspath(__file__))


def build(path):
    con = sqlite3.connect(path)
    with open(os.path.join(HERE, "schema.sql"), encoding="utf-8") as f:
        con.executescript(f.read())
    con.executemany("INSERT INTO customers VALUES (?,?,?)", [(1, "Aoki", "a@x"), (2, "Baba", None), (3, "Chiba", "c@x")])
    con.executemany("INSERT INTO addresses VALUES (?,?,?,?)", [(1, 1, "Tokyo", 1), (2, 2, "Osaka", 1), (3, 3, "Nagoya", 1)])
    con.executemany("INSERT INTO products VALUES (?,?,?)", [(1, "pen", 120), (2, "notebook", 300), (3, "bag", 2500), (4, "ink", 80)])
    con.executemany("INSERT INTO orders VALUES (?,?,?)", [(1, 1, "2026-03-01"), (2, 1, "2026-04-02"), (3, 3, "2026-04-05")])
    con.executemany("INSERT INTO order_items VALUES (?,?,?)", [(1, 1, 2), (1, 2, 1), (2, 3, 1), (3, 4, 5)])
    con.commit()
    return con


if __name__ == "__main__":
    build(sys.argv[1]).close()
