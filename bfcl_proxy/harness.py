#!/usr/bin/env python3
"""Agent harness: an OpenAI Responses-API proxy that sits in front of llama-server
and makes a local model a more reliable tool-calling agent.

Graph per request:
  prep (agent system prompt)
   -> generate (model)
   -> validate (instant, deterministic: JSON, names, types, enums, required; auto-repair + fan-out)
        -> errors left? feed them back and regenerate (loop, max RETRIES)
   -> judge (fast typed micro-judgments on the same model, JSON-schema constrained, logprob confidence)
        coverage: turn start, calls made   -> missing actions? regenerate with the gap named
        finish:   after tool results, text -> task not done? regenerate with "continue: ..."
   -> respond

Everything runs locally (stdlib only). Usage:
  harness.py --upstream http://127.0.0.1:8085 --port 8086 [--no-judge] [--no-prompt] [--no-validate]
"""
import argparse, copy, json, math, sys, threading, time, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AGENT_PROMPT = """You are a precise function-calling agent. Rules:
1. Do every action the user asked for. When the request has several independent tasks, or repeats a task with different values (e.g. "then repeat with...", "for A, B and C"), emit one function call per task, all in the same response.
2. Each argument must match its declared type. Never pack several values into one string or number argument; make separate calls instead.
3. Copy values from the request exactly. Follow each parameter's description for units and formats.
4. Call a function only if it can really do what was asked. If no function fits, or a required value is missing and cannot be found with the tools, answer in plain text and say why.
5. For multi-step tasks, keep calling functions until every requested action is done. Check the current state with the tools instead of guessing. Do not stop early and do not ask for confirmation when you can proceed.
6. Leave optional arguments out unless the request needs them."""

RETRIES = 2
MAX_OUT = 2048  # a looping model otherwise runs to the context limit and blocks the server
JUDGE_CONF = 0.75  # act on a judgment only when its probability is at least this
MISSING_CONF = 0.9  # the coverage judge fires more often in multi-step tasks, so it needs more certainty

log_lock = threading.Lock()
def log(**kw):
    with log_lock:
        print(json.dumps({"t": round(time.time(), 2), **kw}, ensure_ascii=False), file=sys.stderr, flush=True)


def post(url, body, timeout=900):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


# ---------- validate: deterministic checks and repairs ----------

def _num(v, kind):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        if kind == "integer":
            return int(v) if float(v).is_integer() else None
        return v
    if isinstance(v, str):
        s = v.strip().replace(",", "")
        try:
            f = float(s)
        except ValueError:
            return None
        if kind == "integer":
            return int(f) if f.is_integer() else None
        return int(f) if f.is_integer() and "." not in s else f
    return None


def coerce(v, schema):
    """Return (value, ok). Repairs common type slips; ok=False if unrecoverable."""
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), None)
    if "enum" in schema and v not in schema["enum"] and isinstance(v, str):
        for e in schema["enum"]:
            if isinstance(e, str) and e.lower() == v.lower():
                return e, True
        return v, False
    if t in ("integer", "number"):
        n = _num(v, t)
        return (n, True) if n is not None else (v, False)
    if t == "boolean":
        if isinstance(v, bool):
            return v, True
        if isinstance(v, str) and v.lower() in ("true", "false"):
            return v.lower() == "true", True
        return v, False
    if t == "string":
        if isinstance(v, str):
            return v, True
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return str(v), True
        return v, False
    if t == "array":
        if isinstance(v, str):
            try:
                p = json.loads(v)
                if isinstance(p, list):
                    v = p
            except ValueError:
                pass
        if not isinstance(v, list):
            return v, False
        items = schema.get("items") or {}
        out, ok = [], True
        for x in v:
            y, o = coerce(x, items) if items else (x, True)
            out.append(y); ok &= o
        return out, ok
    if t == "object":
        if isinstance(v, str):
            try:
                v = json.loads(v)
            except ValueError:
                return v, False
        if not isinstance(v, dict):
            return v, False
        props = schema.get("properties")
        if props:
            for k in list(v):
                if k in props:
                    v[k], _ = coerce(v[k], props[k])
        return v, True
    return v, True


def validate_calls(calls, tools):
    """calls: list of {name, arguments(str)}. Returns (fixed_calls, errors)."""
    by_name = {t["name"]: t for t in tools if t.get("type") == "function"}
    fixed, errors = [], []
    for c in calls:
        name = c["name"]
        if name not in by_name:
            errors.append(f"`{name}` is not an available function. Available: {', '.join(by_name)}")
            continue
        try:
            args = json.loads(c["arguments"] or "{}")
            if not isinstance(args, dict):
                raise ValueError
        except ValueError:
            errors.append(f"`{name}`: arguments are not a valid JSON object: {c['arguments'][:200]}")
            continue
        params = by_name[name].get("parameters") or {}
        props = params.get("properties") or {}
        for k in [k for k in args if props and k not in props]:
            del args[k]
        # fan-out: a scalar parameter that received a list -> one call per element
        fan = {k: v for k, v in args.items() if k in props and isinstance(v, list)
               and props[k].get("type") in ("string", "integer", "number", "boolean") and len(v) > 1}
        variants = [args]
        if fan:
            n = max(len(v) for v in fan.values())
            if all(len(v) in (1, n) for v in fan.values()):
                variants = []
                for i in range(n):
                    a = dict(args)
                    for k, v in fan.items():
                        a[k] = v[i] if len(v) == n else v[0]
                    variants.append(a)
                log(event="fanout", name=name, n=n)
        for a in variants:
            bad = []
            for k, v in list(a.items()):
                if isinstance(v, list) and len(v) == 1 and props.get(k, {}).get("type") in ("string", "integer", "number", "boolean"):
                    v = v[0]
                nv, ok = coerce(v, props.get(k, {}))
                a[k] = nv
                if not ok:
                    bad.append(f"`{k}` must be {props.get(k, {}).get('type')}{' one of ' + str(props[k]['enum']) if 'enum' in props.get(k, {}) else ''}, got {json.dumps(v)[:80]}")
            miss = [r for r in params.get("required", []) if r not in a]
            if miss:
                bad.append("missing required " + ", ".join(f"`{m}`" for m in miss))
            if bad:
                errors.append(f"`{name}`: " + "; ".join(bad))
            fixed.append({"name": name, "arguments": json.dumps(a, ensure_ascii=False)})
    return fixed, errors


# ---------- judge: fast typed micro-judgments ----------

def tool_digest(tools, limit=6000):
    lines = []
    for t in tools:
        if t.get("type") != "function":
            continue
        props = (t.get("parameters") or {}).get("properties") or {}
        lines.append(f"- {t['name']}({', '.join(props)}): {(t.get('description') or '')[:200]}")
    s = "\n".join(lines)
    return s[:limit]


def judge(upstream, question, key, explain=None):
    """Fast typed micro-judgment: one constrained boolean (a few tokens), probability from logprobs.
    Only when the verdict will be acted on, a second short call asks for the reason (`explain`)."""
    def ask(props, max_tokens):
        body = {"messages": [{"role": "user", "content": question}], "temperature": 0, "max_tokens": max_tokens,
                "logprobs": True, "top_logprobs": 5,
                "response_format": {"type": "json_schema", "json_schema": {"name": "j", "strict": True, "schema": {
                    "type": "object", "properties": props, "required": list(props)}}},
                "chat_template_kwargs": {"enable_thinking": False}}
        return post(upstream + "/v1/chat/completions", body, timeout=120)["choices"][0]
    t0 = time.time()
    ch = ask({key: {"type": "boolean"}}, 24)
    raw = ch["message"]["content"]
    try:
        obj = json.loads(raw)
    except ValueError:
        log(event="judge_bad_json", raw=raw[:120])
        return {key: None}, 0.0
    p = 1.0
    for tok in (ch.get("logprobs") or {}).get("content") or []:
        if tok["token"].strip()[:1] in ("t", "f"):
            p = math.exp(tok["logprob"]); break
    obj["p"] = p
    if explain and obj.get(key) == explain[0] and p >= JUDGE_CONF:
        ch2 = ask({key: {"type": "boolean"}, explain[1]: {"type": "string"}}, 80)
        try:
            obj[explain[1]] = json.loads(ch2["message"]["content"]).get(explain[1], "")
        except ValueError:
            pass
    log(event="judge", key=key, value=obj.get(key), p=round(p, 3), ms=int((time.time() - t0) * 1000))
    return obj, p


def text_of(item):
    c = item.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(x.get("text", "") for x in c if isinstance(x, dict))
    return ""


def last_user_text(inp):
    for it in reversed(inp):
        if it.get("role") == "user":
            return text_of(it)
    return ""


def transcript_tail(inp, n=12):
    out = []
    for it in inp[-n:]:
        if it.get("role") in ("user", "assistant"):
            out.append(f"{it['role'].upper()}: {text_of(it)[:600]}")
        elif it.get("type") == "function_call":
            out.append(f"CALL: {it.get('name')}({it.get('arguments')[:300]})")
        elif it.get("type") == "function_call_output":
            out.append(f"RESULT: {str(it.get('output'))[:300]}")
    return "\n".join(out)


# ---------- the graph ----------

class Harness:
    def __init__(self, upstream, use_prompt=True, use_validate=True, use_judge=True):
        self.up, self.use_prompt, self.use_validate, self.use_judge = upstream, use_prompt, use_validate, use_judge
        self.active = use_prompt or use_validate or use_judge

    def generate(self, body, extra_input):
        b = copy.deepcopy(body)
        b["input"] = b["input"] + extra_input
        b.setdefault("temperature", 0.001)
        b["max_output_tokens"] = min(int(b.get("max_output_tokens") or MAX_OUT), MAX_OUT)
        return post(self.up + "/v1/responses", b)

    def run(self, body):
        body = copy.deepcopy(body)
        if isinstance(body.get("input"), str):
            body["input"] = [{"role": "user", "content": body["input"]}]
        for k in ("include", "reasoning", "store"):
            body.pop(k, None)
        tools = body.get("tools") or []
        inp = body["input"]
        if self.use_prompt and tools:
            body["input"] = [{"role": "system", "content": AGENT_PROMPT}] + inp
        turn_start = bool(inp) and inp[-1].get("role") == "user"
        extra, resp = [], None
        for attempt in range(RETRIES + 1):
            resp = self.generate(body, extra)
            calls = [o for o in resp["output"] if o.get("type") == "function_call"]
            feedback = None
            if calls and self.use_validate and tools:
                fixed, errors = validate_calls(calls, tools)
                if errors and attempt < RETRIES:
                    feedback = "Your function calls had errors:\n- " + "\n- ".join(errors) + "\nIssue the complete, corrected set of function calls."
                    log(event="validate_retry", errors=errors)
                else:
                    resp["output"] = self.rebuild(resp["output"], fixed)
                    calls = [o for o in resp["output"] if o.get("type") == "function_call"]
            if feedback is None and self.use_judge and tools and attempt < RETRIES:
                try:
                    feedback = self.judge_step(inp, tools, calls, resp, turn_start)
                except Exception as e:  # a broken judgment must never break the answer
                    log(event="judge_error", err=repr(e)[:200])
                    feedback = None
            if feedback is None:
                break
            prev = [{"type": "function_call", "call_id": c["call_id"], "name": c["name"], "arguments": c["arguments"]} for c in calls]
            msg = [o for o in resp["output"] if o.get("type") == "message"]
            # show the model its draft as plain text (no fake call ids in the history), then the critique
            draft = "; ".join(f"{c['name']}({c['arguments']})" for c in prev) or (text_of(msg[0]) if msg else "")
            extra = [{"role": "user", "content": f"[Checker] Your draft response was: {draft[:2000]}\n{feedback}"}]
        return resp

    def rebuild(self, output, fixed):
        tmpl = next(o for o in output if o.get("type") == "function_call")
        rest = [o for o in output if o.get("type") != "function_call"]
        out = []
        for i, f in enumerate(fixed):
            o = dict(tmpl); o.update(f)
            o["id"] = f"{tmpl['id']}_{i}"; o["call_id"] = f"{tmpl['call_id']}_{i}"
            out.append(o)
        return rest + out

    def judge_step(self, inp, tools, calls, resp, turn_start):
        req = last_user_text(inp)
        if calls and turn_start:
            q = (f"A user asked an assistant:\n<request>\n{req[:3000]}\n</request>\nAvailable functions:\n{tool_digest(tools)}\n"
                 f"The assistant made these calls:\n" + "\n".join(f"- {c['name']}({c['arguments']})" for c in calls) +
                 "\n\nIgnore steps that must wait for the result of an earlier call. Among the actions that can be done right now, "
                 "did the assistant leave any requested action out (for example a repeat with different values, or one of several items)? "
                 "Answer missing=true only if an action is clearly left out.")
            obj, p = judge(self.up, q, "missing", (True, "what"))
            if obj.get("missing") and p >= MISSING_CONF:
                return (f"You may have left out an action of the LATEST user request: {obj.get('what', '')}. "
                        "Issue the complete set of function calls for the latest request only, including the ones in your draft. "
                        "Calls from earlier turns are already done; do not repeat them. "
                        "If that action needs the result of another call first, issue only the calls you can make now.")
        if not calls and not turn_start:
            text = " ".join(text_of(o) for o in resp["output"] if o.get("type") == "message")
            q = (f"Conversation so far (most recent last):\n{transcript_tail(inp)}\nASSISTANT (final reply): {text[:800]}\n\n"
                 f"The user's latest request was:\n<request>\n{req[:2000]}\n</request>\nAvailable functions:\n{tool_digest(tools, 3000)}\n\n"
                 "Has the assistant already carried out every action in the latest request with function calls? "
                 "Answer done=false only if a requested action that the functions can perform has clearly not been done yet.")
            obj, p = judge(self.up, q, "done", (False, "next"))
            if obj.get("done") is False and p >= JUDGE_CONF:
                return f"The task is not finished yet: {obj.get('next', '')}. Continue by calling the needed functions."
        return None


class Handler(BaseHTTPRequestHandler):
    harness = None

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(n) or b"{}")
        try:
            if self.path.rstrip("/").endswith("/responses"):
                if not self.harness.active:
                    out = self.harness.generate(body, [])
                else:
                    try:
                        out = self.harness.run(body)
                    except Exception as e:  # fail safe: fall back to the plain model answer
                        log(event="harness_fallback", err=repr(e)[:200])
                        out = self.harness.generate(body, [])
            else:
                out = post(self.harness.up + self.path, body)
            code = 200
        except Exception as e:  # report upstream failures as an API error
            log(event="error", err=repr(e))
            out, code = {"error": {"message": repr(e), "type": "harness_error"}}, 500
        data = json.dumps(out).encode()
        self.send_response(code); self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        try:
            with urllib.request.urlopen(self.harness.up + self.path, timeout=30) as r:
                data, code = r.read(), r.status
        except Exception as e:
            data, code = repr(e).encode(), 502
        self.send_response(code); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--upstream", default="http://127.0.0.1:8085")
    ap.add_argument("--port", type=int, default=8086)
    ap.add_argument("--no-prompt", action="store_true")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args()
    Handler.harness = Harness(a.upstream, not a.no_prompt, not a.no_validate, not a.no_judge)
    ThreadingHTTPServer(("127.0.0.1", a.port), Handler).serve_forever()
