"""CSV import.  Columns: date,amount,currency,category,note (currency/note may be empty)."""
import csv
from collections import Counter
from decimal import Decimal

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


def key(e):
    return (e.date, Decimal(e.amount), e.currency, e.category, e.note)


def import_csv(store, path):
    """Validate every row first (all or nothing), then add the rows not yet in the store.

    A key that occurs n times in the file and m times in the store is added n - m times.
    Returns (added, skipped)."""
    pending = []
    for n, row in read_rows(path):
        try:
            pending.append(make_expense(0, row.get("date"), row.get("amount"), row.get("currency"),
                                        row.get("category"), row.get("note")))
        except ValidationError as e:
            raise ImportError_(f"{path}:{n}: {e}") from None
    have = Counter(key(e) for e in store.expenses)
    added = 0
    for e in pending:
        k = key(e)
        if have[k] > 0:
            have[k] -= 1
            continue
        store.add(lambda i, e=e: make_expense(i, e.date, e.amount, e.currency, e.category, e.note))
        added += 1
    return added, len(pending) - added
