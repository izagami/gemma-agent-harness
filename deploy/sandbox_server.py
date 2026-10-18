#!/usr/bin/env python3
"""Command runner for the agent. Runs in its own container on an internal-only network (no internet), sharing
the workspace volume with the agent server. POST /exec {"cmd", "cwd" (relative to /workspaces), "timeout"}."""
import json, os, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.realpath(os.environ.get("WORKSPACE_ROOT", "/workspaces"))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        if self.path != "/exec":
            self.send_response(404); self.end_headers(); return
        d = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        cwd = os.path.realpath(os.path.join(ROOT, d.get("cwd", ".")))
        if not (cwd == ROOT or cwd.startswith(ROOT + os.sep)) or not os.path.isdir(cwd):
            out = {"code": 2, "stdout": "", "stderr": "invalid working directory"}
        else:
            t = max(1, min(int(d.get("timeout", 60)), 600))
            try:
                r = subprocess.run(["timeout", "-s", "KILL", str(t), "bash", "-lc", d.get("cmd", "")], cwd=cwd,
                                   capture_output=True, text=True, timeout=t + 10)
                out = {"code": r.returncode, "stdout": r.stdout[-200000:], "stderr": r.stderr[-50000:]}
            except subprocess.TimeoutExpired:
                out = {"code": 124, "stdout": "", "stderr": f"timed out after {t} s"}
        b = json.dumps(out).encode()
        self.send_response(200); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8700"))), H).serve_forever()
