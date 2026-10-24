"""Data access for the shop web app (docs/REPO.md)."""


def _customer(row):
    return {"id": row[0], "name": row[1], "city": row[2]}


def list_customers(con):
    rows = con.execute("""
        SELECT c.id, c.name, a.city
        FROM customers c JOIN addresses a ON a.customer_id = c.id
        ORDER BY c.name, c.id""").fetchall()
    return [_customer(r) for r in rows]


def find_customer(con, name):
    row = con.execute(f"""
        SELECT c.id, c.name, a.city
        FROM customers c LEFT JOIN addresses a ON a.customer_id = c.id AND a.is_primary = 1
        WHERE c.name = '{name}' ORDER BY c.id LIMIT 1""").fetchone()
    return _customer(row) if row else None


def order_counts_since(con, day):
    return con.execute("""
        SELECT c.name, COUNT(o.id)
        FROM customers c LEFT JOIN orders o ON o.customer_id = c.id
        WHERE o.ordered_at >= ?
        GROUP BY c.id
        ORDER BY COUNT(o.id) DESC, c.name, c.id""", (day,)).fetchall()


def search_products(con, text):
    rows = con.execute(f"SELECT name FROM products WHERE name LIKE '%{text}%' ORDER BY name, id").fetchall()
    return [r[0] for r in rows]


def products_page(con, size, after=None):
    if after is None:
        rows = con.execute("SELECT id, name, price FROM products ORDER BY price DESC, id LIMIT ?", (size,)).fetchall()
    else:
        rows = con.execute("SELECT id, name, price FROM products WHERE price < ? ORDER BY price DESC, id LIMIT ?",
                           (after, size)).fetchall()
    cursor = rows[-1][2] if len(rows) == size else None
    return [r[1] for r in rows], cursor


def orders_with_items(con, customer_id):
    out = []
    for oid, day in con.execute("SELECT id, ordered_at FROM orders WHERE customer_id = ? ORDER BY ordered_at, id",
                                (customer_id,)).fetchall():
        items = con.execute("""
            SELECT p.name, i.qty, p.price FROM order_items i JOIN products p ON p.id = i.product_id
            WHERE i.order_id = ? ORDER BY p.name, p.id""", (oid,)).fetchall()
        out.append({"id": oid, "ordered_at": day, "items": items, "total": sum(q * p for _, q, p in items)})
    return out
