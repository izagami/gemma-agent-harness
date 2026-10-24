"""Reading and writing CSV tables."""
import csv


def normalize(name):
    """Header names are matched case-insensitively (docs/SPEC.md)."""
    return name.lower()


def read_table(path):
    """Return (columns, rows): the normalised column names in file order and one dict per data row."""
    with open(path, encoding="utf-8", newline="") as f:
        text = f.read()
    columns, rows = None, []
    for line in text.splitlines():
        if not line.strip():
            continue
        fields = next(csv.reader([line]))
        if columns is None:
            columns = [normalize(c) for c in fields]
            continue
        fields += [""] * (len(columns) - len(fields))
        rows.append(dict(zip(columns, fields)))
    return columns or [], rows


def write_table(path, columns, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(columns)
        for r in rows:
            w.writerow([r.get(c, "") for c in columns])
