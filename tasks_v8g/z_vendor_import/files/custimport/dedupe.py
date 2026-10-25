"""Decide whether an incoming record is a customer we already know.

Rules (first match wins):
  1. the record's source id was imported before          -> "skip"
  2. same e-mail address                                 -> "merge"
  3. same name AND same phone number (both non-empty)    -> "merge"
  otherwise                                              -> "new"
"""
from custimport import normalize


class Index:
    def __init__(self, customers=()):
        self.by_source = {}
        self.by_email = {}
        self.by_name_phone = {}
        for c in customers:
            self.add(c)

    def add(self, c):
        for s in c.sources:
            self.by_source[s] = c
        if c.email:
            self.by_email.setdefault(normalize.email_key(c.email), c)
        if c.name and c.phone:
            self.by_name_phone.setdefault((normalize.name_key(c.name), normalize.phone_key(c.phone)), c)

    def match(self, rec):
        """(action, customer or None)."""
        c = self.by_source.get(rec.source)
        if c is not None:
            return "skip", c
        if rec.email:
            c = self.by_email.get(normalize.email_key(rec.email))
            if c is not None:
                return "merge", c
        if rec.name and rec.phone:
            c = self.by_name_phone.get((normalize.name_key(rec.name), normalize.phone_key(rec.phone)))
            if c is not None:
                return "merge", c
        return "new", None
