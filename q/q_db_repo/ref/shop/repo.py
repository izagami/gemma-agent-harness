"""Data access for the shop web app (docs/REPO.md)."""

CUSTOMER = """SELECT c.id, c.name, a.city
              FROM customers c LEFT JOIN addresses a ON a.customer_id = c.id AND a.is_primary = 1"""


def _customer(row):
    return {"id": row[0], "name": row[1], "city": row[2]}


def list_customers(con):
    return [_customer(r) for r in con.execute(CUSTOMER + " ORDER BY c.name, c.id").fetchall()]


def find_customer(con, name):
    row = con.execute(CUSTOMER + " WHERE c.name = ? ORDER BY c.id LIMIT 1", (name,)).fetchone()
    return _customer(row) if row else None


def order_counts_since(con, day):
    return con.execute("""
        SELECT c.name, COUNT(o.id)
        FROM customers c LEFT JOIN orders o ON o.customer_id = c.id AND o.ordered_at >= ?
        GROUP BY c.id
        ORDER BY COUNT(o.id) DESC, c.name, c.id""", (day,)).fetchall()


def search_products(con, text):
    esc = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    rows = con.execute("SELECT name FROM products WHERE name LIKE ? ESCAPE '\\' ORDER BY name, id",
                       ("%" + esc + "%",)).fetchall()
    return [r[0] for r in rows]


def products_page(con, size, after=None):
    if after is None:
        rows = con.execute("SELECT id, name, price FROM products ORDER BY price DESC, id LIMIT ?", (size + 1,)).fetchall()
    else:
        price, pid = after
        rows = con.execute("""SELECT id, name, price FROM products WHERE price < ? OR (price = ? AND id > ?)
                              ORDER BY price DESC, id LIMIT ?""", (price, price, pid, size + 1)).fetchall()
    more = len(rows) > size
    rows = rows[:size]
    return [r[1] for r in rows], ((rows[-1][2], rows[-1][0]) if more else None)


def orders_with_items(con, customer_id):
    orders = con.execute("SELECT id, ordered_at FROM orders WHERE customer_id = ? ORDER BY ordered_at, id",
                         (customer_id,)).fetchall()
    items = {}
    for oid, name, qty, price in con.execute("""
            SELECT i.order_id, p.name, i.qty, p.price
            FROM order_items i JOIN products p ON p.id = i.product_id JOIN orders o ON o.id = i.order_id
            WHERE o.customer_id = ? ORDER BY p.name, p.id""", (customer_id,)):
        items.setdefault(oid, []).append((name, qty, price))
    return [{"id": oid, "ordered_at": day, "items": items.get(oid, []),
             "total": sum(q * p for _, q, p in items.get(oid, []))} for oid, day in orders]
