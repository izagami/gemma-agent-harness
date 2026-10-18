import unittest

from app.errors import NotFound
from app.http import Request, ok
from app.router import Router


class RouterTest(unittest.TestCase):
    def setUp(self):
        self.r = Router()
        self.r.add("GET", "/things/{id:int}", lambda ctx, req: ok({"id": req.params["id"], "q": req.query}))
        self.r.add("GET", "/things/{name}/tags", lambda ctx, req: ok({"name": req.params["name"]}))
        self.r.add("GET", "/boom", lambda ctx, req: (_ for _ in ()).throw(NotFound("nope")))

    def test_int_param_and_query(self):
        res = self.r.dispatch(None, Request("GET", "/things/42?x=1&y=two"))
        self.assertEqual(res.status, 200)
        self.assertEqual(res.body, {"id": 42, "q": {"x": "1", "y": "two"}})

    def test_str_param(self):
        res = self.r.dispatch(None, Request("GET", "/things/abc/tags"))
        self.assertEqual(res.body, {"name": "abc"})

    def test_not_found(self):
        res = self.r.dispatch(None, Request("GET", "/things/abc"))
        self.assertEqual((res.status, res.body), (404, {"error": "not_found"}))

    def test_method_not_allowed(self):
        res = self.r.dispatch(None, Request("DELETE", "/things/1"))
        self.assertEqual((res.status, res.body), (405, {"error": "method_not_allowed"}))

    def test_api_error_becomes_response(self):
        res = self.r.dispatch(None, Request("GET", "/boom"))
        self.assertEqual((res.status, res.body), (404, {"error": "not_found", "detail": "nope"}))
