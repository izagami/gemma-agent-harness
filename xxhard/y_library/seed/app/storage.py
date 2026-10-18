"""Very small table store. Rows are dicts with an integer "id" assigned on insert.

With a path, every change is written to a JSON file and Storage(path) loads it back,
so data survives a restart. Ids are never reused, even after deletes.
"""
import copy
import json
import os


class Storage:
    def __init__(self, path=None):
        self.path = path
        self.tables = {}   # table -> {id: row}
        self.seq = {}      # table -> last id
        if path and os.path.exists(path):
            self._load()

    def _load(self):
        with open(self.path, encoding="utf-8") as f:
            data = json.load(f)
        self.tables = {t: {int(k): v for k, v in rows.items()} for t, rows in data["tables"].items()}
        self.seq = dict(data["seq"])

    def _save(self):
        if not self.path:
            return
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"tables": self.tables, "seq": self.seq}, f, ensure_ascii=False)
        os.replace(tmp, self.path)

    def insert(self, table, row):
        new_id = self.seq.get(table, 0) + 1
        self.seq[table] = new_id
        row = dict(row, id=new_id)
        self.tables.setdefault(table, {})[new_id] = row
        self._save()
        return copy.deepcopy(row)

    def get(self, table, row_id):
        row = self.tables.get(table, {}).get(row_id)
        return copy.deepcopy(row) if row is not None else None

    def update(self, table, row_id, changes):
        rows = self.tables.get(table, {})
        if row_id not in rows:
            return None
        rows[row_id].update(changes)
        rows[row_id]["id"] = row_id
        self._save()
        return copy.deepcopy(rows[row_id])

    def delete(self, table, row_id):
        rows = self.tables.get(table, {})
        if row_id not in rows:
            return False
        del rows[row_id]
        self._save()
        return True

    def find(self, table, **where):
        """Rows whose fields equal all the given values, in id order."""
        rows = self.tables.get(table, {})
        return [copy.deepcopy(r) for _, r in sorted(rows.items())
                if all(r.get(k) == v for k, v in where.items())]
