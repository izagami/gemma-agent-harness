"""CSV import.  Columns: date,amount,currency,category,note (currency/note may be empty)."""
import csv

from exp.models import ValidationError, make_expense

COLUMNS = ("date", "amount", "currency", "category", "note")


class ImportError_(Exception):
    pass


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        missing = [c for c in ("date", "amount", "category") if c not in (reader.fieldnames or [])]
        if missing:
            raise ImportError_(f"{path}: missing column(s): {', '.join(missing)}")
        for n, row in enumerate(reader, 2):
            yield n, row


def import_csv(store, path):
    """Validate every row first (all or nothing), then add them.  Returns the number added."""
    pending = []
    for n, row in read_rows(path):
        try:
            pending.append(make_expense(0, row.get("date"), row.get("amount"), row.get("currency"),
                                        row.get("category"), row.get("note")))
        except ValidationError as e:
            raise ImportError_(f"{path}:{n}: {e}") from None
    for e in pending:
        store.add(lambda i, e=e: make_expense(i, e.date, e.amount, e.currency, e.category, e.note))
    return len(pending)
