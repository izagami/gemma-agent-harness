import unittest
from datetime import date

from app.main import create_app


class LoansTest(unittest.TestCase):
    def setUp(self):
        self.day = [date(2026, 10, 1)]
        self.app = create_app(today=lambda: self.day[0])
        for i in range(5):
            self.app.handle("POST", "/books", {"title": f"b{i}", "author": "a"})
        self.app.handle("POST", "/members", {"name": "m", "email": "m@x.jp"})

    def loan(self, book, member=1, **kw):
        return self.app.handle("POST", "/loans", {"book_id": book, "member_id": member, **kw})

    def test_create(self):
        r = self.loan(1)
        self.assertEqual(r.status, 201)
        self.assertEqual(r.body["due_on"], "2026-10-15")

    def test_conflict(self):
        self.loan(1)
        self.assertEqual(self.loan(1).body["detail"], "book already on loan")

    def test_limit(self):
        for b in (1, 2, 3):
            self.loan(b)
        self.assertEqual(self.loan(4).body["detail"], "loan limit reached")

    def test_return(self):
        self.loan(1)
        self.assertEqual(self.app.handle("POST", "/loans/1/return").status, 200)
        self.assertEqual(self.app.handle("POST", "/loans/1/return").status, 409)

    def test_delete_blocked(self):
        self.loan(1)
        self.assertEqual(self.app.handle("DELETE", "/books/1").status, 409)

    def test_overdue(self):
        self.loan(1, days=1)
        self.day[0] = date(2026, 10, 3)
        self.assertEqual(len(self.app.handle("GET", "/loans/overdue").body["loans"]), 1)
