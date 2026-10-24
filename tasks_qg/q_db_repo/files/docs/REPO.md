# shop.repo

Data access functions used by the web app. Every function takes an open `sqlite3.Connection` and returns plain
Python values (dicts/lists/tuples) exactly as below. Inputs come from users: any text (quotes, `%`, `_`, `\`) must work.

* `list_customers(con)` -> one dict per customer `{"id", "name", "city"}`; `city` is the city of the customer's
  primary address, or None when there is none. Order: name, then id.
* `find_customer(con, name)` -> the dict (same keys) of the customer whose name is exactly `name`
  (lowest id if several), or None.
* `order_counts_since(con, day)` -> list of `(name, count)` for EVERY customer, where count is the number of
  their orders with `ordered_at >= day` (0 if none). Order: count descending, then name, then id.
* `search_products(con, text)` -> list of product names that contain `text` literally (ASCII letters
  case-insensitive; `%` and `_` are ordinary characters). Order: name, then id.
* `products_page(con, size, after=None)` -> `(names, cursor)`: products ordered by price descending, then id
  ascending; at most `size` of them that come after `after` in this order. `cursor` is an opaque value to pass as
  `after` for the next page, or None when there are no more products. Following the cursors lists every product
  exactly once.
* `orders_with_items(con, customer_id)` -> list of `{"id", "ordered_at", "items": [(product name, qty, price)],
  "total"}` for the customer's orders, ordered by ordered_at then id; items ordered by product name then product id;
  orders without items have `items == []` and total 0. total = sum(qty * price). Must run at most 2 SQL statements
  in total, whatever the number of orders (the order page is slow otherwise).
