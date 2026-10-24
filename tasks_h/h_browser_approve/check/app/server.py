#!/usr/bin/env python3
"""購買申請の承認システム(デモ)。
usage: python3 app/server.py [--port 8772] [--data app/data/requests.json] [--store store.json] [--delay 200,800]
                             [--seed 1] [--user demo:demo123]
--delay: API の応答を MIN〜MAX ミリ秒ランダムに遅らせる。
申請の状態と操作記録(承認ボタンが押された記録。処理済みで断られたものも含む)は --store の JSON に書く。"""
import argparse, copy, http.cookies, json, os, random, secrets, threading, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
ap = argparse.ArgumentParser()
ap.add_argument("--port", type=int, default=int(os.environ.get("APP_PORT", "8772")))
ap.add_argument("--data", default=os.path.join(HERE, "data", "requests.json"))
ap.add_argument("--store", default="store.json")
ap.add_argument("--delay", default="200,800")
ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--user", default="demo:demo123")
A = ap.parse_args()
USER, PASS = A.user.split(":", 1)
LO, HI = map(int, A.delay.split(","))
REQS = json.load(open(A.data, encoding="utf-8"))
AUDIT = []
RNG, LOCK, SESSIONS = random.Random(A.seed), threading.Lock(), {}


def delay():
    with LOCK:
        ms = RNG.randint(LO, HI)
    time.sleep(ms / 1000)


def save():
    json.dump({"requests": REQS, "audit": AUDIT}, open(A.store, "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def num(no):
    return int(no.split("-")[1])


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

    def user(self):
        c = http.cookies.SimpleCookie(self.headers.get("Cookie", ""))
        return SESSIONS.get(c["sid"].value) if "sid" in c else None

    def body(self):
        return json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        if u.path in ("/", "/login"):
            return self.send(200, open(os.path.join(HERE, "static", "login.html"), encoding="utf-8").read())
        if not self.user():
            if u.path.startswith("/api/"):
                return self.json({"error": "login required"}, 401)
            return self.send(302, "", headers=[("Location", "/login")])
        if u.path == "/requests":
            return self.send(200, open(os.path.join(HERE, "static", "requests.html"), encoding="utf-8").read())
        if u.path == "/api/requests":
            delay()
            kw = q.get("q", "").strip().lower()
            with LOCK:
                hits = [copy.deepcopy(r) for r in REQS if kw in r["no"].lower() or kw in r["title"].lower()]
            hits.sort(key=lambda r: -num(r["no"]))          # newest first
            return self.json({"total": len(hits), "items": hits[:50]})
        self.send(404, "not found")

    def do_POST(self):
        if self.path == "/api/login":
            d = self.body()
            delay()
            if d.get("user") == USER and d.get("password") == PASS:
                sid = secrets.token_hex(8)
                SESSIONS[sid] = USER
                return self.json({"ok": True}, headers=[("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")])
            return self.json({"ok": False, "error": "ユーザー名またはパスワードが違います"}, 403)
        who = self.user()
        if self.path == "/api/approve" and who:
            d = self.body()
            delay()
            with LOCK:
                r = next((x for x in REQS if x["no"] == d.get("no")), None)
                if r is None:
                    return self.json({"ok": False, "error": "申請が見つかりません"}, 404)
                ok = r["status"] == "申請中"
                AUDIT.append({"no": r["no"], "by": who, "comment": d.get("comment", ""), "result": "ok" if ok else "rejected"})
                if ok:
                    r.update(status="承認済", approver=who, comment=d.get("comment", ""))
                save()
            if not ok:
                return self.json({"ok": False, "error": f"{r['no']} は処理済みです({r['status']})"}, 409)
            return self.json({"ok": True, "no": r["no"]})
        self.send(404, "not found")


if __name__ == "__main__":
    ThreadingHTTPServer(("127.0.0.1", A.port), H).serve_forever()
