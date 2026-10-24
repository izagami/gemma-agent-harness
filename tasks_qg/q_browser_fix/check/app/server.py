#!/usr/bin/env python3
"""経費申請システム(デモ)。usage: python3 app/server.py [--port 8766] [--store store.json] [--delay 200,600] [--seed 1]
--delay: APIの応答を MIN〜MAX ミリ秒ランダムに遅らせる。登録された申請は --store の JSON ファイルに書く。"""
import argparse, http.cookies, json, os, random, re, secrets, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "8766")))
ap.add_argument("--store", default="store.json")
ap.add_argument("--delay", default="200,600")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--user", default="demo:demo123")
A = ap.parse_args()
USER, PASS = A.user.split(":", 1)
DEPTS = [("acct", "経理部"), ("sales", "営業部"), ("dev", "開発部"), ("hr", "人事部")]
LO, HI = map(int, A.delay.split(","))
RNG, LOCK, SESSIONS, RECORDS = random.Random(A.seed), threading.Lock(), set(), []


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
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(b)

    def json(self, d, code=200, headers=()):
        self.send(code, json.dumps(d, ensure_ascii=False), "application/json; charset=utf-8", headers)

    def authed(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return "sid" in c and c["sid"].value in SESSIONS

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        pages = {"/": "login.html", "/login": "login.html", "/apply": "apply.html", "/apply/form": "form.html"}
        if u.path in ("/", "/login") or (u.path in pages and self.authed()):
            return self.send(200, open(os.path.join(HERE, "static", pages[u.path]), encoding="utf-8").read())
        if not self.authed():
            return self.json({"error": "login required"}, 401) if u.path.startswith("/api/") else self.send(302, "", headers=[("Location", "/login")])
        if u.path == "/api/depts":
            delay()
            return self.json([{"code": c, "name": n} for c, n in DEPTS])
        self.send(404, "not found")

    def do_POST(self):
        if self.path == "/api/login":
            d = self.body()
            delay()
            if d.get("user") == USER and d.get("password") == PASS:
                sid = secrets.token_hex(8)
                SESSIONS.add(sid)
                return self.json({"ok": True}, headers=[("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")])
            return self.json({"ok": False, "error": "ユーザー名またはパスワードが違います"}, 403)
        if self.path == "/api/apply" and self.authed():
            d = self.body()
            delay()
            ok = (d.get("name", "").strip() and "@" in d.get("email", "") and d.get("dept") in dict(DEPTS)
                  and re.fullmatch(r"[0-9]+", d.get("amount", "")) and d.get("reason", "").strip())
            if not ok:
                return self.json({"ok": False, "error": "入力内容を確認してください"}, 400)
            with LOCK:
                no = f"A-{len(RECORDS) + 1:04d}"
                RECORDS.append({"no": no, "name": d["name"], "email": d["email"], "dept": d["dept"],
                                "amount": int(d["amount"]), "reason": d["reason"]})
                json.dump(RECORDS, open(A.store, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            return self.json({"ok": True, "no": no})
        self.send(404, "not found")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
