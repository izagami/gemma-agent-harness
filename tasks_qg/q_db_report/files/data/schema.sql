CREATE TABLE customers (
    id     INTEGER PRIMARY KEY,
    name   TEXT NOT NULL,
    region TEXT              -- NULL = region not registered yet
);
CREATE TABLE categories (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE
);
CREATE TABLE products (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    deleted     INTEGER NOT NULL DEFAULT 0   -- 1 = no longer sold (old orders still refer to it)
);
CREATE TABLE orders (
    id          INTEGER PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),   -- NULL = guest checkout
    ordered_at  TEXT NOT NULL,                      -- 'YYYY-MM-DD'
    status      TEXT NOT NULL CHECK (status IN ('paid', 'cancelled'))
);
CREATE TABLE order_items (
    order_id   INTEGER NOT NULL REFERENCES orders(id),
    product_id INTEGER NOT NULL REFERENCES products(id),
    qty        INTEGER NOT NULL,
    unit_price INTEGER NOT NULL      -- yen, price at the time of the order
);
