"""JSON customer store.

File format (UTF-8, indent=2, ensure_ascii=False):
  {"next_id": <int>, "customers": [{"id", "name", "email", "phone", "sources": [...]}, ...]}
"""
import json
import os

from custimport.dedupe import Index
from custimport.model import Customer


class Store:
    def __init__(self, path):
        self.path = path
        self.next_id = 1
        self.customers = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                d = json.load(f)
            self.next_id = d["next_id"]
            self.customers = [Customer.from_json(c) for c in d["customers"]]
        self.index = Index(self.customers)

    def save(self):
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"next_id": self.next_id, "customers": [c.to_json() for c in self.customers]},
                      f, ensure_ascii=False, indent=2)
            f.write("\n")
        os.replace(tmp, self.path)

    def apply(self, rec):
        """Insert or merge one record; returns "new", "merge" or "skip"."""
        action, c = self.index.match(rec)
        if action == "skip":
            return action
        if action == "new":
            c = Customer(self.next_id, rec.name, rec.email, rec.phone, [rec.source])
            self.next_id += 1
            self.customers.append(c)
        else:
            c.sources.append(rec.source)
            if not c.email and rec.email:
                c.email = rec.email
            if not c.phone and rec.phone:
                c.phone = rec.phone
            if not c.name and rec.name:
                c.name = rec.name
        self.index.add(c)
        return action
