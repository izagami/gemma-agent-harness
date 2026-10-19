#!/usr/bin/env python3
"""OpenAI-compatible server that exposes the local coding agent (harness v7e) as a model for Open WebUI.

Each conversation gets its own workspace directory. The latest user message is the task; earlier turns are
passed along as context. While the agent works, its steps stream as a collapsible "details" block; the final
summary and the list of files changed follow.

Environment:
  AGENT_API      model server chat endpoint (OpenAI-compatible), e.g. http://llama:8080/v1/chat/completions
  AGENT_MODEL    model name sent to that server
  AGENT_API_KEY  optional key for that server
  AGENT_PROFILE  harness profile (default v7e); model "local-cad" uses CAD_PROFILE (default v8c, CadQuery parts)
  CAD_SHARE / CAD_PUBLIC  where finished CAD files are copied and the URL prefix browsers use for them
  SANDBOX_URL    command runner (deploy/sandbox_server.py); unset = local podman sandbox
  WORKSPACE_ROOT where workspaces live (default /workspaces)
  HOST           listen address (default 0.0.0.0; 127.0.0.1 when running on a shared host)
  SERVER_API_KEY optional: require "Authorization: Bearer <key>" from clients
"""
import hashlib, json, os, queue, sys, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import agent_v5

ROOT = os.environ.get("WORKSPACE_ROOT", "/workspaces")
PROFILE = os.environ.get("AGENT_PROFILE", "v7e")
CAD_PROFILE = os.environ.get("CAD_PROFILE", "v8c")
CAD_SHARE = os.environ.get("CAD_SHARE", "")      # folder served to browsers (e.g. by the web server); unset = no publishing
CAD_PUBLIC = os.environ.get("CAD_PUBLIC", "")    # URL prefix of CAD_SHARE as browsers see it, e.g. /videos/cad
CAD_ID = "local-cad"
KEY = os.environ.get("SERVER_API_KEY", "")
MODEL_ID = "local-agent"
LOCK = threading.Lock()  # one task at a time: small local servers slow down sharply with parallel requests


def text_of(c):
    return c if isinstance(c, str) else " ".join(p.get("text", "") for p in c or [] if isinstance(p, dict))


def workspace_for(req, messages):
    # Open WebUI sends a chat id in the body metadata when available; otherwise key on the first user message
    cid = (req.get("metadata") or {}).get("chat_id") or req.get("chat_id") or req.get("user") or ""
    first = next((text_of(m.get("content")) for m in messages if m.get("role") == "user"), "")
    h = hashlib.sha1((cid or first).encode()).hexdigest()[:16]
    d = os.path.join(ROOT, h)
    os.makedirs(d, exist_ok=True)
    return d


def snapshot(d):
    out = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            try:
                out[os.path.relpath(p, d)] = os.path.getmtime(p)
            except OSError:
                pass
    return out


def describe(ev):
    if "step" in ev and ev.get("calls"):
        n, a = ev["calls"][0]
        try:
            a = json.loads(a)
        except ValueError:
            a = {}
        if n == "bash":
            return f"- `$ {a.get('command', '')[:160]}`"
        if n in ("write_file", "edit_file", "read_file"):
            return f"- {n} `{a.get('path', '')}`"
        if n == "think":
            return f"- 考え中: {a.get('thought', '')[:160]}"
        if n == "todo":
            return "- ToDo: " + " / ".join(f"{'✓' if i.get('status') == 'done' else '·'} {i.get('text', '')[:40]}" for i in a.get("items", [])[:6])
        return f"- {n}"
    if "finish_rejected" in ev:
        return "- 確認で差し戻し: " + ev["finish_rejected"][:160].replace("\n", " ")
    return None


def run_agent(task, workdir, emit, profile=PROFILE):
    before = snapshot(workdir)
    summary = {}

    def log(ev):
        line = describe(ev)
        if line:
            emit(line + "\n")
        if "step" in ev and ev.get("calls") and ev["calls"][0][0] == "finish":
            try:
                summary["text"] = json.loads(ev["calls"][0][1]).get("summary", "")
            except ValueError:
                pass

    with LOCK:
        info = agent_v5.run_task(task, workdir, profile, log)
    after = snapshot(workdir)
    hidden = lambda p: p.startswith(".agent/") or "__pycache__" in p
    changed = sorted(p for p in after if before.get(p) != after[p] and not hidden(p))
    return info, summary.get("text", ""), changed


def publish_cad(workdir):
    """Copy the part's files to CAD_SHARE under an unguessable folder; return markdown plus a machine-readable line."""
    import shutil
    files = {e: os.path.join(workdir, f"model.{e}") for e in ("png", "step", "stl", "glb")}
    if not os.path.exists(files["step"]):
        return "\n（model.step ができていません）\n"
    try:
        report = open(os.path.join(workdir, ".agent", "cad_report.txt")).read()
    except OSError:
        report = ""
    if not (CAD_SHARE and CAD_PUBLIC):
        return "\n" + "".join(f"- `{p}`\n" for p in files.values() if os.path.exists(p))
    key = uuid.uuid4().hex
    dst = os.path.join(CAD_SHARE, key)
    os.makedirs(dst)
    urls = {}
    for e, p in files.items():
        if os.path.exists(p):
            shutil.copy(p, os.path.join(dst, f"part.{e}"))
            urls[e] = f"{CAD_PUBLIC}/{key}/part.{e}"
    md = (f"\n![part]({urls['png']})\n" if "png" in urls else "") + " / ".join(f"[{e.upper()}]({u})" for e, u in urls.items() if e != "png")
    return md + "\n\n<!-- cad-files " + json.dumps(urls) + " -->\n" + (f"\n```\n{report[:1500]}\n```\n" if report else "")


def previews(workdir, changed, n=3, limit=1500):
    """Contents of the first few small text outputs (data files before scripts), so a calling chat model can report results."""
    out = []
    for p in sorted(changed, key=lambda p: p.endswith((".py", ".sh"))):
        try:
            with open(os.path.join(workdir, p), encoding="utf-8") as f:
                t = f.read(limit + 1)
        except (OSError, UnicodeDecodeError):
            continue
        out.append(f"\n`{p}`:\n```\n{t[:limit]}{'\n…（以下省略）' if len(t) > limit else ''}\n```\n")
        if len(out) == n:
            break
    return ("\n<details><summary>ファイルの中身</summary>\n" + "".join(out) + "\n</details>\n") if out else ""


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *a):
        pass

    def _auth(self):
        return not KEY or self.headers.get("Authorization", "") == "Bearer " + KEY

    def _json(self, obj, code=200):
        b = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.rstrip("/").endswith("/health"):
            return self._json({"status": "ok"})
        if not self._auth():
            return self._json({"error": "unauthorized"}, 401)
        if self.path.rstrip("/").endswith("/models"):
            return self._json({"object": "list", "data": [{"id": CAD_ID, "object": "model", "owned_by": "local", "name": "3D部品モデリング (12B, CadQuery)"},
                                                           {"id": MODEL_ID, "object": "model", "owned_by": "local",
                                                            "name": "ローカル作業エージェント (12B)"}]})
        self._json({"error": "not found"}, 404)

    def do_POST(self):
        if not self._auth():
            return self._json({"error": "unauthorized"}, 401)
        if not self.path.rstrip("/").endswith("/chat/completions"):
            return self._json({"error": "not found"}, 404)
        req = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        msgs = req.get("messages") or []
        task = text_of(next((m.get("content") for m in reversed(msgs) if m.get("role") == "user"), ""))
        prior = [f"{m['role']}: {text_of(m.get('content'))[:1500]}" for m in msgs[:-1] if m.get("role") in ("user", "assistant")][-6:]
        if prior:
            task = "Earlier conversation (for context):\n" + "\n".join(prior) + "\n\nCurrent request:\n" + task
        task += "\n\n(Write the finish summary in the same language as the request.)"
        cad = req.get("model") == CAD_ID
        workdir = workspace_for(req, msgs)
        cid, created = "chatcmpl-" + uuid.uuid4().hex[:12], int(time.time())
        q = queue.Queue()
        result = {}

        def worker():
            try:
                result["v"] = run_agent(task, workdir, q.put, CAD_PROFILE if cad else PROFILE)
            except Exception as e:
                result["err"] = f"{type(e).__name__}: {e}"
            q.put(None)

        threading.Thread(target=worker, daemon=True).start()

        def final_text():
            if "err" in result:
                return f"\n</details>\n\nエラー: {result['err']}"
            info, summ, changed = result["v"]
            files = "\n".join(f"- `{p}`" for p in changed[:50]) or "（なし）"
            status = "完了" if info.get("finished") else f"ステップ上限（{info.get('steps')}）で停止"
            return (f"\n</details>\n\n**{status}**（{info.get('seconds')} 秒）\n\n{summ}\n\n**変更したファイル**（作業フォルダ `{workdir}`）\n{files}\n"
                    + (publish_cad(workdir) if cad else previews(workdir, changed)))

        if not req.get("stream"):
            buf = []
            while (x := q.get()) is not None:
                buf.append(x)
            return self._json({"id": cid, "object": "chat.completion", "created": created, "model": MODEL_ID,
                               "choices": [{"index": 0, "message": {"role": "assistant",
                                                                    "content": "<details><summary>作業ログ</summary>\n\n" + "".join(buf) + final_text()},
                                            "finish_reason": "stop"}]})
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream"); self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked"); self.end_headers()

        def send(s, finish=None):
            ev = {"id": cid, "object": "chat.completion.chunk", "created": created, "model": MODEL_ID,
                  "choices": [{"index": 0, "delta": {"content": s} if s else {}, "finish_reason": finish}]}
            data = ("data: " + json.dumps(ev, ensure_ascii=False) + "\n\n").encode()
            self.wfile.write(f"{len(data):x}\r\n".encode() + data + b"\r\n"); self.wfile.flush()

        try:
            send("<details><summary>作業ログ</summary>\n\n")
            while (x := q.get()) is not None:
                send(x)
            send(final_text()); send("", "stop")
            done = b"data: [DONE]\n\n"
            self.wfile.write(f"{len(done):x}\r\n".encode() + done + b"\r\n0\r\n\r\n"); self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            pass


if __name__ == "__main__":
    os.makedirs(ROOT, exist_ok=True)
    ThreadingHTTPServer((os.environ.get("HOST", "0.0.0.0"), int(os.environ.get("PORT", "8094"))), H).serve_forever()
