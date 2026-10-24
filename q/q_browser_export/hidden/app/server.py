#!/usr/bin/env python3
"""受注管理(デモ)。usage: python3 app/server.py [--port 8765] [--data app/data/orders.json] [--delay 200,500] [--seed 1]
--delay: 各APIの応答を MIN〜MAX ミリ秒ランダムに遅らせる(実システムの遅さの再現)。"""
import argparse, http.cookies, json, os, random, secrets, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = 10
ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "8765")))
ap.add_argument("--data", default=os.path.join(HERE, "data", "orders.json"))
ap.add_argument("--delay", default="200,500")
ap.add_argument("--seed", type=int, default=1)
A = ap.parse_args()
DATA = json.load(open(A.data, encoding="utf-8"))
ORDERS = sorted(DATA["orders"], key=lambda o: o["id"], reverse=True)  # 画面は新しい順
LO, HI = map(int, A.delay.split(","))
RNG, LOCK, SESSIONS = random.Random(A.seed), threading.Lock(), set()


def delay():
    with LOCK:
        ms = RNG.randint(LO, HI)
    time.sleep(ms / 1000)


def yen(n):
    return "¥{:,}".format(n)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype="text/html; charset=utf-8", headers=()):
        b = body.encode() if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b)))
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def json(self, d, code=200, headers=()):
        self.send(code, json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8", headers)

    def authed(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "sid" in c and c["sid"].value in SESSIONS

    def static(self, name):
        self.send(200, open(os.path.join(HERE, "static", name), encoding="utf-8").read())

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = urllib.parse.parse_qs(u.query)
        if u.path in ("/", "/login"):
            return self.static("login.html")
        if not self.authed():
            if u.path.startswith("/api/"):
                return self.json({"error": "login required"}, 401)
            return self.send(302, "", headers=[("Location", "/login")])
        if u.path == "/orders":
            return self.static("orders.html")
        if u.path == "/api/orders":
            page = max(1, int(q.get("page", ["1"])[0]))
            delay()
            rows = ORDERS[(page - 1) * PAGE: page * PAGE]
            return self.json({"page": page, "pages": max(1, -(-len(ORDERS) // PAGE)), "rows": [
                {"id": o["id"], "customer": o["customer"], "amount": yen(o["amount"]), "status": o["status"]} for o in rows]})
        if u.path.startswith("/api/orders/"):
            oid = urllib.parse.unquote(u.path.rsplit("/", 1)[1])
            delay()
            o = next((o for o in ORDERS if o["id"] == oid), None)
            return self.json({"id": o["id"], "owner": o["owner"], "note": o["note"]}) if o else self.json({}, 404)
        if u.path == "/api/export.csv":
            # 旧機能: 保留中の注文は出力されない(既知の制限)
            lines = ["注文番号,顧客,金額,状態"] + [f'{o["id"]},{o["customer"]},{o["amount"]},{o["status"]}'
                                              for o in ORDERS if o["status"] != "保留"]
            return self.send(200, "\r\n".join(lines) + "\r\n", "text/csv; charset=utf-8")
        self.send(404, "not found")

    def do_POST(self):
        if self.path == "/api/login":
            d = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
            delay()
            if d.get("user") == DATA["user"]["name"] and d.get("password") == DATA["user"]["password"]:
                sid = secrets.token_hex(8)
                SESSIONS.add(sid)
                return self.json({"ok": True}, headers=[("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")])
            return self.json({"ok": False, "error": "ユーザー名またはパスワードが違います"}, 403)
        self.send(404, "not found")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
