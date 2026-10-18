import unittest

from app.main import create_app


class MembersTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app()

    def test_create(self):
        res = self.app.handle("POST", "/members", {"name": "Aoi", "email": " Aoi@Example.com "})
        self.assertEqual(res.status, 201)
        self.assertEqual(res.body, {"id": 1, "name": "Aoi", "email": "aoi@example.com"})

    def test_duplicate_email(self):
        self.app.handle("POST", "/members", {"name": "Aoi", "email": "aoi@example.com"})
        res = self.app.handle("POST", "/members", {"name": "A2", "email": "AOI@example.com"})
        self.assertEqual((res.status, res.body), (409, {"error": "conflict", "detail": "email already registered"}))

    def test_invalid_email(self):
        res = self.app.handle("POST", "/members", {"name": "Aoi", "email": "aoi.example.com"})
        self.assertEqual(res.body, {"error": "validation", "fields": {"email": "invalid email"}})

    def test_missing(self):
        res = self.app.handle("GET", "/members/7")
        self.assertEqual(res.status, 404)
        self.assertEqual(self.app.handle("POST", "/members/7", {}).status, 405)
