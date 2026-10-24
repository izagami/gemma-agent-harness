"""Merging tables keyed by one column."""

KEY = "id"


def merge(tables, key=KEY):
    """tables: list of (columns, rows) in the order given on the command line. Returns (columns, rows)."""
    columns, order, data = [], [], {}
    for cols, rows in tables:
        for c in cols:
            if c not in columns:
                columns.append(c)
        for row in rows:
            k = row.get(key, "")
            if not k:
                continue  # rows without a key cannot be merged
            if k not in data:
                data[k] = {}
                order.append(k)
            data[k].update(row)
    return columns, [data[k] for k in order]
