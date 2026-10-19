#!/usr/bin/env python3
"""Live view of a CAD agent run: the current model in 3D, the four-view drawing, and what the agent is doing.

usage: live.py RUN_DIR [--port 8100]
RUN_DIR holds log.jsonl and work/ (model.glb, model.png), as written by eval.py or a demo run. The page polls
/state every 2 s and reloads the model whenever model.glb changes. Serves on 127.0.0.1 only.
"""
import argparse, json, os, re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

VIEWER_JS = os.path.expanduser("~/video/share/cad/_lib/model-viewer.min.js")

PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>CAD live</title>
<script type="module" src="/mv.js"></script>
<style>
body{margin:0;font:15px/1.45 system-ui,sans-serif;background:#101418;color:#e8edf2;display:grid;
     grid-template-columns:62% 38%;grid-template-rows:auto 1fr 34%;height:100vh}
header{grid-column:1/3;padding:10px 16px;background:#1a2129;display:flex;gap:20px;align-items:baseline}
header b{font-size:20px} #status{color:#9fb3c8}
model-viewer{width:100%;height:100%;background:radial-gradient(#2a3540,#151b21)}
#log{grid-row:2/4;grid-column:2;overflow:hidden;padding:10px 14px;border-left:1px solid #26303a}
.s{margin:0 0 8px;padding:6px 8px;border-radius:6px;background:#18202a;white-space:pre-wrap;word-break:break-word}
.think{border-left:3px solid #8ab4f8}.bash{border-left:3px solid #81c995}.write_file,.edit_file{border-left:3px solid #fdd663}
.obs{color:#9fb3c8;font-size:13px}.finish{border-left:3px solid #f28b82}
#bottom{grid-column:1;display:grid;grid-template-columns:auto 1fr;gap:10px;padding:8px;border-top:1px solid #26303a;overflow:hidden}
#bottom img{height:100%;border-radius:6px;background:#fff}
#report{font:12px/1.35 ui-monospace,monospace;white-space:pre-wrap;color:#cfd8e3;overflow:hidden}
</style></head><body>
<header><b id="ttl">__TITLE__</b><span id="status">待機中</span></header>
<model-viewer id="mv" camera-controls auto-rotate rotation-per-second="20deg" shadow-intensity="0.8" exposure="1.1"></model-viewer>
<div id="log"></div>
<div id="bottom"><img id="png" alt=""><div id="report"></div></div>
<script>
let glb = 0, png = 0;
async function tick() {
  try {
    const s = await (await fetch('/state')).json();
    document.getElementById('status').textContent = s.status;
    if (s.glb && s.glb !== glb) { glb = s.glb; document.getElementById('mv').src = '/model.glb?t=' + glb; }
    if (s.png && s.png !== png) { png = s.png; document.getElementById('png').src = '/model.png?t=' + png; }
    document.getElementById('report').textContent = s.report || '';
    const log = document.getElementById('log'); log.innerHTML = '';
    for (const e of s.events.slice().reverse()) {
      const d = document.createElement('div'); d.className = 's ' + e.kind; d.textContent = e.text; log.appendChild(d);
    }
  } catch (err) {}
}
setInterval(tick, 2000); tick();
</script></body></html>"""


def events(run, n=14):
    path = os.path.join(run, "log.jsonl")
    out, steps, done = [], 0, None
    try:
        lines = open(path, encoding="utf-8").read().splitlines()
    except OSError:
        return [], 0, None
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if "step" in e and e.get("calls"):
            steps = e["step"]
            for name, a in e["calls"]:
                try:
                    a = json.loads(a)
                except ValueError:  # the log keeps only the first 1500 characters of each call
                    a = {k: json.loads('"' + v + '"') if v.count('"') % 2 == 0 else v
                         for k, v in re.findall(r'"(thought|command|path)"\s*:\s*"((?:[^"\\]|\\.)*)', a)}
                text = a.get("thought") or a.get("command") or (f"{a.get('path', '')} を書く" if name in ("write_file", "edit_file") else name)
                out.append({"kind": name, "text": f"{e['step']}. {text}"[:420]})
        elif "obs" in e and out:
            out.append({"kind": "obs", "text": e["obs"][:260]})
        elif "finish_rejected" in e:
            out.append({"kind": "finish", "text": "差し戻し: " + e["finish_rejected"][:300]})
        elif "result" in e:
            done = e["result"]
    return out[-n:], steps, done


class H(BaseHTTPRequestHandler):
    run = "."
    title = "12B CAD エージェント — ライブ"

    hits = 0

    def log_message(self, *a):
        H.hits += 1

    def send(self, body, ctype, code=200):
        self.send_response(code); self.send_header("Content-Type", ctype); self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        work = os.path.join(self.run, "work")
        if p == "/":
            page = PAGE.replace("__TITLE__", self.title)
            if "compact=1" in self.path:  # one panel of the wall: model on top, steps below, no drawing
                page = page.replace("grid-template-columns:62% 38%;grid-template-rows:auto 1fr 34%",
                                    "grid-template-columns:100%;grid-template-rows:auto 55% 1fr")
                page = page.replace("#log{grid-row:2/4;grid-column:2;", "#log{grid-row:3;grid-column:1;font-size:13px;")
                page = page.replace("#bottom{grid-column:1;display:grid", "#bottom{display:none")
            return self.send(page.encode(), "text/html; charset=utf-8")
        if p == "/wall":  # several runs side by side: /wall?ports=8100,8101,8102
            ports = [x for x in self.path.split("ports=")[-1].split(",") if x.isdigit()] if "ports=" in self.path else []
            frames = "".join(f'<iframe src="http://127.0.0.1:{x}/?compact=1"></iframe>' for x in ports)
            wall = ("<!doctype html><meta charset=utf-8><title>CAD wall</title><style>body{margin:0;background:#000;display:grid;"
                    f"grid-template-columns:repeat({max(1, len(ports))},1fr);height:100vh;gap:4px}}iframe{{border:0;width:100%;height:100%}}"
                    f"</style>{frames}")
            return self.send(wall.encode(), "text/html; charset=utf-8")
        if p == "/mv.js":
            return self.send(open(VIEWER_JS, "rb").read(), "text/javascript")
        if p in ("/model.glb", "/model.png"):
            f = os.path.join(work, p[1:])
            if os.path.exists(f):
                return self.send(open(f, "rb").read(), "model/gltf-binary" if p.endswith("glb") else "image/png")
            return self.send(b"", "text/plain", 404)
        if p == "/hits":
            return self.send(str(H.hits).encode(), "text/plain")
        if p == "/state":
            ev, steps, done = events(self.run)
            mt = lambda f: int(os.path.getmtime(os.path.join(work, f)) * 1000) if os.path.exists(os.path.join(work, f)) else 0
            rep = ""
            for f in (os.path.join(work, ".agent", "cad_report.txt"),):
                if os.path.exists(f):
                    rep = open(f, encoding="utf-8").read()
            if not rep:  # latest cadtool output seen in the log
                for e in reversed(ev):
                    if e["kind"] == "obs" and "bounding box" in e["text"]:
                        rep = e["text"]; break
            status = (done.get("label") or f"完了 ({done.get('steps')} ステップ, {done.get('seconds')} 秒)" if done and done.get("finished")
                      else f"停止 ({done.get('steps')} ステップ)" if done else f"作業中: {steps} ステップ目")
            return self.send(json.dumps({"status": status, "glb": mt("model.glb"), "png": mt("model.png"), "events": ev,
                                         "report": rep}, ensure_ascii=False).encode(), "application/json")
        self.send(b"not found", "text/plain", 404)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("run"); ap.add_argument("--port", type=int, default=8100); ap.add_argument("--title")
    a = ap.parse_args()
    H.title = a.title or H.title
    H.run = os.path.abspath(a.run)
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()
