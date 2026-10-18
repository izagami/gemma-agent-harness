#!/usr/bin/env python3
"""Local coding agent: a Claude-Code-style tool loop for a local model (llama-server, OpenAI chat API).

Every command runs inside a network-less podman container that only sees the task workspace.
The harness (prompt, loop control, verification) is configured by a profile so variants can be compared.
"""
import json, os, re, subprocess, time, urllib.request, uuid

API = os.environ.get("AGENT_API", "http://127.0.0.1:8085/v1/chat/completions")
IMAGE = "docker.io/library/python:3.12-slim"
OBS_LIMIT = 6000

TOOLS = [
    {"type": "function", "function": {"name": "bash", "description": "Run a shell command in /work (bash -lc). Returns exit code, stdout and stderr. 60 s timeout. No network.",
     "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file (path relative to /work). Returns the content with line numbers.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Create or overwrite a file with the given content.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}}},
    {"type": "function", "function": {"name": "edit_file", "description": "Replace one exact occurrence of old_text with new_text in a file. old_text must match the file exactly and be unique.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}}},
    {"type": "function", "function": {"name": "finish", "description": "Call when the task is fully done and verified. Give a short summary of what you did.",
     "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}},
]


class Sandbox:
    def __init__(self, workdir):
        self.name = "agent-" + uuid.uuid4().hex[:8]
        subprocess.run(["podman", "run", "-d", "--rm", "--name", self.name, "--network", "none", "--userns=keep-id",
                        "-v", f"{workdir}:/work:Z", "-w", "/work", IMAGE, "sleep", "infinity"], check=True, capture_output=True)

    def sh(self, cmd, timeout=60):
        try:
            r = subprocess.run(["podman", "exec", "-w", "/work", self.name, "timeout", "-s", "KILL", str(timeout), "bash", "-lc", cmd],
                               capture_output=True, text=True, timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            return 124, "", f"timed out after {timeout} s"
        if r.returncode in (124, 137):
            return r.returncode, r.stdout, r.stderr + f"\n(command killed: exceeded {timeout} s)"
        return r.returncode, r.stdout, r.stderr

    def close(self):
        subprocess.run(["podman", "rm", "-f", "-t", "0", self.name], capture_output=True)


def clip(s, n=OBS_LIMIT):
    if len(s) <= n:
        return s
    return s[: n // 2] + f"\n... [{len(s) - n} chars cut] ...\n" + s[-n // 2:]


def safe_path(p):
    p = p.strip()
    if p.startswith("/work/"):
        p = p[6:]
    if p.startswith("/") or ".." in p.split("/"):
        raise ValueError("path must stay inside /work")
    return p


def run_tool(box, workdir, name, args):
    if name == "bash":
        code, out, err = box.sh(args["command"])
        return clip(f"exit code: {code}\n--- stdout ---\n{out}\n--- stderr ---\n{err}")
    if name == "read_file":
        p = os.path.join(workdir, safe_path(args["path"]))
        with open(p, encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
        return clip("\n".join(f"{i + 1:4d}| {l}" for i, l in enumerate(lines)))
    if name == "write_file":
        p = os.path.join(workdir, safe_path(args["path"]))
        os.makedirs(os.path.dirname(p) or workdir, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(args["content"])
        return f"wrote {len(args['content'])} chars to {args['path']}"
    if name == "edit_file":
        p = os.path.join(workdir, safe_path(args["path"]))
        with open(p, encoding="utf-8") as f:
            s = f.read()
        n = s.count(args["old_text"])
        if n != 1:
            return f"error: old_text found {n} times (must be exactly 1). Read the file and copy the text exactly."
        with open(p, "w", encoding="utf-8") as f:
            f.write(s.replace(args["old_text"], args["new_text"]))
        return "edited"
    return f"error: unknown tool {name}"


def chat(messages, tools, max_tokens=2048, temperature=0.3):
    body = {"messages": messages, "tools": tools, "max_tokens": max_tokens, "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": False}}
    req = urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=900) as r:
        return json.load(r)["choices"][0]


def run_task(task_text, workdir, profile, log):
    """Returns dict(steps, finished, seconds)."""
    import harness_profiles as hp
    prof = hp.PROFILES[profile]
    box = Sandbox(workdir)
    t0 = time.time()
    messages = [{"role": "system", "content": prof["system"]}, {"role": "user", "content": task_text}]
    finished, steps = False, 0
    state = hp.LoopState()
    try:
        for steps in range(1, prof["max_steps"] + 1):
            msgs = hp.view(messages, prof)
            ch = chat(msgs, TOOLS, temperature=prof["temperature"])
            m = ch["message"]
            calls = m.get("tool_calls") or []
            entry = {"role": "assistant", "content": m.get("content") or ""}
            if calls:
                entry["tool_calls"] = calls
            messages.append(entry)
            log({"step": steps, "content": entry["content"][:2000], "calls": [(c["function"]["name"], c["function"]["arguments"][:1500]) for c in calls]})
            if not calls:
                nudge = hp.on_no_call(state, prof, entry["content"])
                if nudge is None:
                    break
                messages.append({"role": "user", "content": nudge}); log({"nudge": nudge})
                continue
            done_now = False
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except ValueError:
                    obs = "error: arguments were not valid JSON. Call the tool again with valid JSON."
                    args = None
                if args is not None:
                    if name == "finish":
                        check = hp.on_finish(state, prof, box, task_text, messages, args)
                        if check is None:
                            obs, done_now = "finished", True
                        else:
                            obs = check; log({"finish_rejected": check[:1000]})
                    else:
                        try:
                            obs = run_tool(box, workdir, name, args)
                        except Exception as e:
                            obs = f"error: {e}"
                obs = hp.on_observation(state, prof, name, args, obs)
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": obs})
                log({"obs": obs[:1500]})
            if done_now:
                finished = True
                break
    finally:
        box.close()
    return {"steps": steps, "finished": finished, "seconds": round(time.time() - t0, 1)}
