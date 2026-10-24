"""JSON file store.

The file looks like {"next_id": 4, "expenses": [{...}, ...]}.  A missing file is an
empty store.  Writes go to a temporary file first and are renamed into place.
"""
import json
import os
import tempfile

from exp.models import Expense


class StoreError(Exception):
    pass


class Store:
    def __init__(self, path):
        self.path = path
        self.next_id = 1
        self.expenses = []
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
            self.next_id = int(data["next_id"])
            self.expenses = [Expense.from_dict(d) for d in data["expenses"]]
        except (ValueError, KeyError, TypeError) as e:
            raise StoreError(f"corrupt store {self.path}: {e}") from None

    def add(self, make):
        """make(id) -> Expense; the store assigns the id."""
        exp = make(self.next_id)
        self.next_id += 1
        self.expenses.append(exp)
        return exp

    def save(self):
        d = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(d, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".exp-", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"next_id": self.next_id, "expenses": [e.to_dict() for e in self.expenses]},
                      f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.path)

    def in_range(self, start, end):
        """Expenses with start <= date <= end (ISO strings), in id order."""
        return [e for e in self.expenses if start <= e.date <= end]
