"""Build data/shop.db (sample data) from data/schema.sql: python3 data/make_db.py"""
import os, sqlite3

HERE = os.path.dirname(os.path.abspath(__file__))
CUSTOMERS = [(1, "Aoki", "kanto"), (2, "Baba", "kanto"), (3, "Chiba", "kansai"), (4, "Doi", "kansai"),
             (5, "Endo", None), (6, "Fujii", "kanto"), (7, "Goto", "kyushu")]
CATEGORIES = [(1, "books"), (2, "food"), (3, "toys")]
PRODUCTS = [(1, "novel", 1, 0), (2, "manga", 1, 0), (3, "rice", 2, 0), (4, "tea", 2, 1), (5, "robot", 3, 0)]
ORDERS = [  # id, customer, date, status, [(product, qty, price)]
    (1, 1, "2026-01-05", "paid", [(1, 2, 1200), (3, 1, 3000)]),
    (2, 2, "2026-01-20", "paid", [(5, 1, 8000)]),
    (3, 3, "2026-01-20", "cancelled", [(5, 2, 8000)]),
    (4, 3, "2026-03-02", "paid", [(4, 4, 500), (2, 3, 600)]),
    (5, 1, "2026-03-15", "paid", [(5, 1, 7500)]),
    (6, 4, "2026-03-15", "paid", [(3, 2, 3000), (1, 1, 1200)]),
    (7, None, "2026-04-01", "paid", [(2, 5, 600)]),
    (8, 6, "2026-04-10", "cancelled", [(1, 1, 1200)]),
    (9, 5, "2026-04-28", "paid", [(4, 2, 500)]),
]


def build(path, customers=CUSTOMERS, categories=CATEGORIES, products=PRODUCTS, orders=ORDERS):
    if os.path.exists(path):
        os.remove(path)
    con = sqlite3.connect(path)
    con.executescript(open(os.path.join(HERE, "schema.sql"), encoding="utf-8").read())
    con.executemany("INSERT INTO customers VALUES (?,?,?)", customers)
    con.executemany("INSERT INTO categories VALUES (?,?)", categories)
    con.executemany("INSERT INTO products VALUES (?,?,?,?)", products)
    for oid, cid, day, status, items in orders:
        con.execute("INSERT INTO orders VALUES (?,?,?,?)", (oid, cid, day, status))
        con.executemany("INSERT INTO order_items VALUES (?,?,?,?)", [(oid, p, q, u) for p, q, u in items])
    con.commit()
    con.close()


if __name__ == "__main__":
    build(os.path.join(HERE, "shop.db"))
