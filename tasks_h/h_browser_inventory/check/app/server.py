#!/usr/bin/env python3
"""在庫照会システム(デモ)。
usage: python3 app/server.py [--port 8770] [--data app/data/stock.json] [--delay 100,500] [--seed 1] [--user demo:demo123]
--delay: API の応答を MIN〜MAX ミリ秒ランダムに遅らせる。"""
import argparse, http.cookies, json, os, random, secrets, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "8770")))
ap.add_argument("--data", default=os.path.join(HERE, "data", "stock.json"))
ap.add_argument("--delay", default="100,500")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--user", default="demo:demo123")
A = ap.parse_args()
USER, PASS = A.user.split(":", 1)
LO, HI = map(int, A.delay.split(","))
DATA = json.load(open(A.data, encoding="utf-8"))
RNG, LOCK, SESSIONS = random.Random(A.seed), threading.Lock(), set()


def delay():
    with LOCK:
        ms = RNG.randint(LO, HI)
    time.sleep(ms / 1000)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        self.send_header("Cache-Control", "no-store")
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def json(self, d, code=200, headers=()):
        self.send(code, json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8", headers)

    def authed(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "sid" in c and c["sid"].value in SESSIONS

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path in ("/", "/login"):
            return self.send(200, open(os.path.join(HERE, "static", "login.html"), encoding="utf-8").read())
        if not self.authed():
            if u.path.startswith("/api/"):
                return self.json({"error": "login required"}, 401)
            return self.send(302, "", headers=[("Location", "/login")])
        if u.path == "/stock":
            return self.send(200, open(os.path.join(HERE, "static", "stock.html"), encoding="utf-8").read())
        if u.path == "/api/warehouses":
            delay()
            return self.json([{"code": w["code"], "name": w["name"]} for w in DATA["warehouses"]])
        if u.path == "/api/stock":
            delay()
            wh = next((w for w in DATA["warehouses"] if w["code"] == q.get("wh")), None)
            if wh is None:
                return self.json({"error": "unknown warehouse"}, 404)
            items = sorted(wh["items"], key=lambda it: it["loc"])
            if q.get("instock", "1") == "1":
                items = [it for it in items if it["qty"] > 0]
            off, lim = int(q.get("offset", 0)), min(int(q.get("limit", 20)), 20)
            return self.json({"total": len(items), "items": items[off:off + lim]})
        self.send(404, "not found")

    def do_POST(self):
        if self.path == "/api/login":
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            delay()
            if d.get("user") == USER and d.get("password") == PASS:
                sid = secrets.token_hex(8)
                SESSIONS.add(sid)
                return self.json({"ok": True}, headers=[("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")])
            return self.json({"ok": False, "error": "ユーザー名またはパスワードが違います"}, 403)
        self.send(404, "not found")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
