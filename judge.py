"""Fast typed micro-judgments (Jev-style, fully local): one constrained boolean from the same llama-server,
a few tokens of output, probability from logprobs. Typical server time ~0.2 s."""
import json, math, os, time, urllib.request

API = os.environ.get("AGENT_API", "http://127.0.0.1:8185/v1/chat/completions")
MODEL = os.environ.get("AGENT_MODEL", "local")
HEADERS = {"Content-Type": "application/json", "Authorization": "Bearer " + os.environ.get("AGENT_API_KEY", "none")}


JEV_LOG = os.environ.get("JEV_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", "jev.jsonl"))


def conf(ch):
    """probability of the value token; only tokens after the ':' count (a key such as "violated" contains "ted")"""
    after = False
    for tok in (ch.get("logprobs") or {}).get("content") or []:
        t = tok["token"].strip()
        if not after:
            after = ":" in t
            t = t.split(":", 1)[1].strip() if after else ""
        if after and t[:1] in ("t", "f"):
            return math.exp(tok["logprob"])
    return 1.0


def log(key, val, p, t0):
    """every judgment goes to runs/jev.jsonl so the watchdog can see stuck or broken judgments while a run goes on"""
    try:
        with open(JEV_LOG, "a") as f:
            pt = p if val else 1 - p if val is False else 0.5   # ask() returns the confidence of its answer; log p(true)
            f.write(json.dumps({"t": round(time.time(), 1), "pid": os.getpid(), "key": key, "val": val, "p": round(pt, 3),
                                "ms": int((time.time() - t0) * 1000)}) + "\n")
    except OSError:
        pass


def ask(question, key, max_tokens=24):
    """Returns (value: bool | None, p: float, ms: int). None when the output could not be read."""
    body = {"model": MODEL, "messages": [{"role": "user", "content": question}], "temperature": 0, "max_tokens": max_tokens,
            "logprobs": True, "top_logprobs": 3,
            "response_format": {"type": "json_schema", "json_schema": {"name": "j", "strict": True, "schema": {
                "type": "object", "properties": {key: {"type": "boolean"}}, "required": [key]}}},
            "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    try:
        req = urllib.request.Request(API, json.dumps(body).encode(), HEADERS)
        with urllib.request.urlopen(req, timeout=120) as r:
            ch = json.load(r)["choices"][0]
        val = json.loads(ch["message"]["content"]).get(key)
    except Exception:
        return None, 0.0, int((time.time() - t0) * 1000)
    p = conf(ch)
    log(key, val, p, t0)
    return val, p, int((time.time() - t0) * 1000)


def evidence(messages, n=14, width=700):
    """Compact transcript tail: what the agent did and what it saw."""
    out = []
    for m in messages[-n:]:
        if m["role"] == "assistant":
            for c in m.get("tool_calls") or []:
                out.append(f"ACTION {c['function']['name']}: {c['function']['arguments'][:width]}")
            if m.get("content"):
                out.append("SAID: " + m["content"][:300])
        elif m["role"] == "tool":
            out.append("RESULT: " + m["content"][:width])
    return "\n".join(out)


def ask_in_context(messages, tools, question, key, max_tokens=24):
    """Same judgment, but asked as a continuation of the agent's own conversation (same tools, same prefix),
    so llama-server reuses the cached prompt and only the question is processed."""
    msgs = list(messages)
    if msgs and msgs[-1].get("tool_calls"):
        msgs = msgs + [{"role": "tool", "tool_call_id": c.get("id", ""), "content": "(awaiting review)"} for c in msgs[-1]["tool_calls"]]
    if msgs and msgs[-1]["role"] == "user":
        msgs = msgs + [{"role": "assistant", "content": "(noted)"}]
    msgs = msgs + [{"role": "user", "content": "[harness question, answer only in JSON] " + question}]
    body = {"model": MODEL, "messages": msgs, "tools": tools, "temperature": 0, "max_tokens": max_tokens, "logprobs": True, "top_logprobs": 3,
            "response_format": {"type": "json_schema", "json_schema": {"name": "j", "strict": True, "schema": {
                "type": "object", "properties": {key: {"type": "boolean"}}, "required": [key]}}},
            "chat_template_kwargs": {"enable_thinking": False}}
    t0 = time.time()
    try:
        req = urllib.request.Request(API, json.dumps(body).encode(), HEADERS)
        with urllib.request.urlopen(req, timeout=120) as r:
            ch = json.load(r)["choices"][0]
        val = json.loads(ch["message"]["content"]).get(key)
    except Exception:
        return None, 0.0, int((time.time() - t0) * 1000)
    p = conf(ch)
    log(key, val, p, t0)
    return val, p, int((time.time() - t0) * 1000)
