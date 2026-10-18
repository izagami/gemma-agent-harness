import unittest
from datetime import date

from app.main import create_app


class BooksTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app(today=lambda: date(2026, 10, 1))

    def post_book(self, **kw):
        body = {"title": "こころ", "author": "夏目漱石", **kw}
        return self.app.handle("POST", "/books", body)

    def test_create_and_get(self):
        res = self.post_book(year=1914)
        self.assertEqual(res.status, 201)
        self.assertEqual(res.body, {"id": 1, "title": "こころ", "author": "夏目漱石", "year": 1914})
        self.assertEqual(self.app.handle("GET", "/books/1").body["title"], "こころ")

    def test_year_optional(self):
        self.assertIsNone(self.post_book().body["year"])

    def test_validation(self):
        res = self.app.handle("POST", "/books", {"title": "", "year": "1914", "isbn": "x"})
        self.assertEqual(res.status, 400)
        self.assertEqual(res.body, {"error": "validation", "fields": {
            "author": "required", "isbn": "unknown field",
            "title": "must not be empty", "year": "must be an integer"}})

    def test_list_filter(self):
        self.post_book()
        self.app.handle("POST", "/books", {"title": "羅生門", "author": "芥川龍之介"})
        res = self.app.handle("GET", "/books?author=芥川龍之介")
        self.assertEqual([b["title"] for b in res.body["books"]], ["羅生門"])

    def test_update_and_delete(self):
        self.post_book()
        res = self.app.handle("PATCH", "/books/1", {"year": 1914})
        self.assertEqual(res.body["year"], 1914)
        self.assertEqual(self.app.handle("DELETE", "/books/1").status, 204)
        res = self.app.handle("GET", "/books/1")
        self.assertEqual((res.status, res.body), (404, {"error": "not_found", "detail": "book not found"}))
