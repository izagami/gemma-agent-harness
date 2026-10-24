#!/usr/bin/env python3
"""Graph harness for Gemma 4 26B-A4B (rebuilt from scratch, 2026-10-22).

Instead of one long chat where the model plans, remembers and checks everything itself, the program owns the plan
and the state, and every model call gets a short, freshly built context:

  recon (no model) -> requirements (structured) -> investigators (short read-only agents, parallel)
  -> oracle tests (several independent test files, each case weighed by a fast boolean judge)
  -> repair candidates (short agents on separate copies, parallel) -> execute every candidate x every test case
  -> pick by consensus (CodeT) -> refine the best ones with the failing evidence -> apply the winner.

Work is spread over all lanes (LANES, 2 requests per server). Thinking mode is per stage and per profile.
"""
import ast, concurrent.futures as cf, difflib, json, math, os, re, shutil, threading, time, urllib.error, urllib.request
import agent as base

LANES = [u.rstrip("/") + "/v1/chat/completions" for u in
         os.environ.get("LANES", "http://127.0.0.1:8185,http://127.0.0.1:8186,http://127.0.0.1:8187").split(",")]
PER_LANE = int(os.environ.get("PER_LANE", "2"))

PROFILES = {
    # think: stages that use the model's built-in reasoning
    "gA": {"think": set(), "investigators": 3, "oracles": 4, "candidates": 6, "refine": 4},
    "gB": {"think": {"investigate", "repair", "refine"}, "investigators": 3, "oracles": 4, "candidates": 6, "refine": 4},
}


# ---------------------------------------------------------------- model access

class Pool:
    """At most PER_LANE requests in flight per server; a request goes to the least busy lane."""
    def __init__(self, lanes):
        self.busy = {u: 0 for u in lanes}
        self.cv = threading.Condition()
        self.calls = 0

    def post(self, body, timeout=900):
        with self.cv:
            while min(self.busy.values()) >= PER_LANE:
                self.cv.wait()
            url = min(self.busy, key=self.busy.get)
            self.busy[url] += 1
            self.calls += 1
        try:
            req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)["choices"][0]
        finally:
            with self.cv:
                self.busy[url] -= 1
                self.cv.notify()


POOL = Pool(LANES)


def chat(messages, tools=None, think=False, max_tokens=None, temperature=0.7, schema=None, tool_choice=None):
    body = {"messages": messages, "temperature": temperature,
            "max_tokens": max_tokens or (16384 if think else 8192),
            "chat_template_kwargs": {"enable_thinking": think}}
    if tools:
        body["tools"] = tools
    if tool_choice:
        body["tool_choice"] = tool_choice
    if schema:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "out", "strict": True, "schema": schema}}
    for attempt in range(3):
        try:
            ch = POOL.post(body)
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code == 500 and "tool call" in msg:
                # the call was cut off (usually a huge heredoc/file at max_tokens): the caller tells the model
                return {"content": "", "tool_calls": [], "broken_call": msg}
            if attempt == 2:
                raise RuntimeError(f"server {e.code}: {msg}")
            body["temperature"] = 1.0
            continue
        m = ch["message"]
        if m.get("content") or m.get("tool_calls"):
            return m
        body["temperature"] = 1.0   # Gemma sometimes emits only a stray "<tool_call|>": a glitch, not a decision
    return m


JEV_LOG = os.environ.get("JEV_LOG", os.path.join(os.path.dirname(os.path.abspath(__file__)), "runs", "jev.jsonl"))


def jev_log(key, pv, t0):
    p, val = pv
    try:
        with open(JEV_LOG, "a") as f:
            f.write(json.dumps({"t": round(time.time(), 1), "pid": os.getpid(), "key": key, "val": val, "p": round(p, 3),
                                "ms": int((time.time() - t0) * 1000)}) + "\n")
    except OSError:
        pass
    return p


def judge(question, key="ok"):
    """Fast typed micro-judgment: one constrained boolean, probability from logprobs (~0.2 s). Returns p(True)."""
    t0 = time.time()
    return jev_log(key, _judge(question, key), t0)


def _judge(question, key):
    body = {"messages": [{"role": "user", "content": question}], "temperature": 0, "max_tokens": 16,
            "logprobs": True, "top_logprobs": 3, "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {"type": "json_schema", "json_schema": {"name": "j", "strict": True, "schema": {
                "type": "object", "properties": {key: {"type": "boolean"}}, "required": [key]}}}}
    try:
        ch = POOL.post(body, timeout=120)
        val = json.loads(ch["message"]["content"])[key]
    except Exception:
        return 0.5, None
    # the value token comes after the ':' (q25 10-23: with key "violated" the token "ted" of the key itself was read
    # as true, so every check counted as a violation with p=1.0)
    after = False
    for tok in (ch.get("logprobs") or {}).get("content") or []:
        t = tok["token"].strip()
        if not after:
            after = ":" in t
            t = t.split(":", 1)[1].strip() if after else ""
        if after and t[:1] in ("t", "f"):
            p = math.exp(tok["logprob"])
            return (p if t[:1] == "t" else 1 - p), val
    return (1.0 if val else 0.0), val


def structured(prompt, schema, think=False, system=None):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    m = chat(msgs, think=think, schema=schema, temperature=0.3)
    try:
        return json.loads(m.get("content") or "{}")
    except ValueError:
        return {}


def structured_safe(f, *a):
    try:
        return f(*a)
    except Exception:
        return None


def code_block(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    return max(blocks, key=len) if blocks else (text or "")


# ---------------------------------------------------------------- workspace helpers

SKIP_DIRS = {".git", "__pycache__", ".agent"}


def files_of(root):
    out = []
    for d, dirs, fs in os.walk(root):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for f in sorted(fs):
            out.append(os.path.relpath(os.path.join(d, f), root))
    return out


def decode(b):
    for enc in ("utf-8", "cp932"):   # Excel/VBA exports are often cp932
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            pass
    return b.decode("utf-8", "replace")


def read(root, rel, limit=None):
    try:
        s = decode(open(os.path.join(root, rel), "rb").read())
    except OSError:
        return ""
    return s if limit is None or len(s) <= limit else s[:limit] + f"\n... [{len(s) - limit} more characters]"


def outline(root):
    """File list with sizes; for .py files the top-level classes/functions with line numbers and first doc line."""
    lines = []
    for rel in files_of(root):
        size = os.path.getsize(os.path.join(root, rel))
        lines.append(f"{rel} ({size} bytes)")
        if rel.endswith(".py"):
            try:
                tree = ast.parse(read(root, rel))
            except SyntaxError:
                continue
            for n in tree.body:
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    doc = (ast.get_docstring(n) or "").split("\n")[0][:80]
                    kind = "class" if isinstance(n, ast.ClassDef) else "def"
                    lines.append(f"    {n.lineno}: {kind} {n.name}" + (f"  - {doc}" if doc else ""))
    return "\n".join(lines)


def listing(root, rels, limit=40000):
    out, n = [], 0
    for rel in rels:
        lines = read(root, rel).split("\n")
        block = f"=== {rel} ===\n" + "\n".join(f"{i + 1:4d}| {l}" for i, l in enumerate(lines))
        if n + len(block) > limit:
            out.append(f"=== {rel} === (not shown: too long; read it with read_file)")
            continue
        out.append(block); n += len(block)
    return "\n\n".join(out)


def copy_ws(src, dst):
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
    return dst


def diff(a, b):
    out = []
    for rel in sorted(set(files_of(a)) | set(files_of(b))):
        x, y = read(a, rel), read(b, rel)
        if x != y:
            out += difflib.unified_diff(x.splitlines(), y.splitlines(), "a/" + rel, "b/" + rel, lineterm="", n=2)
    return "\n".join(out)


# ---------------------------------------------------------------- short tool-using agents

T_BASH = base.TOOLS[0]
T_READ = {"type": "function", "function": {"name": "read_file", "description": "Read a text file with line numbers. Optional start/end line numbers for a part of a long file.",
          "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}}}
T_WRITE, T_EDIT = base.TOOLS[2], base.TOOLS[3]
T_REPORT = {"type": "function", "function": {"name": "report", "description": "Give your findings. This ends your investigation.",
            "parameters": {"type": "object", "properties": {
                "observed": {"type": "string", "description": "what you ran and what actually happened (exact commands and the key output lines)"},
                "cause": {"type": "string", "description": "the root cause, as precisely as the evidence allows (file, function, line, why)"},
                "fix_plan": {"type": "string", "description": "what to change, where, and what else must keep working"}},
                "required": ["observed", "cause", "fix_plan"]}}}
T_DONE = {"type": "function", "function": {"name": "done", "description": "Call when your change is complete and you have run the checks.",
          "parameters": {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]}}}


def tool(box, ws, name, args, protected):
    if name == "bash":
        code, out, err = box.sh("export PYTHONPATH=/work; " + args["command"], timeout=90)
        return base.clip(f"exit code: {code}\n--- stdout ---\n{out}\n--- stderr ---\n{err}", 5000)
    if name == "read_file":
        p = os.path.join(ws, base.safe_path(args["path"]))
        lines = decode(open(p, "rb").read()).split("\n")
        a = max(1, int(args.get("start") or 1)); b = min(len(lines), int(args.get("end") or len(lines)))
        return base.clip("\n".join(f"{i:4d}| {lines[i - 1]}" for i in range(a, b + 1)), 8000)
    if name in ("write_file", "edit_file"):
        rel = base.safe_path(args["path"])
        if rel in protected:
            return f"error: {rel} is a provided input that the task says must not change. Leave it as it is."
        return base.run_tool(box, ws, name, args)
    return f"error: unknown tool {name}"


def mini_agent(ws, system, user, tools, final, max_turns, think, protected, log, tag, final_check=None):
    """A short agent with a fresh context. Returns the arguments of the final tool call (or None)."""
    base.SMART_EDIT = True
    box = base.Sandbox(ws)
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    seen = {}
    try:
        for turn in range(1, max_turns + 1):
            last = turn == max_turns
            m = chat(msgs, tools=[t for t in tools if not last or t["function"]["name"] == final], think=think,
                     tool_choice="required", temperature=0.7 if not think else 1.0)
            if m.get("broken_call"):
                log({"agent": tag, "turn": turn, "broken_call": m["broken_call"][:200]})
                msgs.append({"role": "user", "content": "[harness] Your last tool call was cut off (too long) and did not run. "
                             "Write big files in parts: write_file a first part, then add the rest with edit_file, or change "
                             "only the lines that need it with edit_file."})
                continue
            calls = m.get("tool_calls") or []
            entry = {"role": "assistant", "content": m.get("content") or "", "tool_calls": calls}
            if m.get("reasoning_content"):
                entry["reasoning_content"] = m["reasoning_content"]
            msgs.append(entry)
            if not calls:
                msgs.append({"role": "user", "content": "Use a tool."})
                continue
            for c in calls:
                name = c["function"]["name"]
                try:
                    args = json.loads(c["function"]["arguments"] or "{}")
                except ValueError:
                    args = None
                log({"agent": tag, "turn": turn, "call": [name, (c["function"]["arguments"] or "")[:600]]})
                if name == final and args is not None:
                    err = final_check() if final_check and not last else None
                    if not err:
                        return args
                    msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": err})
                    continue
                if args is None:
                    obs = "error: arguments were not valid JSON"
                else:
                    key = json.dumps([name, args], sort_keys=True) + str(sorted((f, os.path.getmtime(os.path.join(ws, f))) for f in files_of(ws)))
                    if key in seen:
                        obs = "[harness] Not run: exactly the same call as before with no file changed since, so the result is the same. Do something else."
                    else:
                        try:
                            obs = tool(box, ws, name, args, protected)
                        except Exception as e:
                            obs = f"error: {e}"
                        seen[key] = True
                left = max_turns - turn
                if left in (3, 1):
                    obs += f"\n[harness] {left} turn(s) left. " + ("Next turn you must call " + final + "." if left == 1 else "Wrap up.")
                msgs.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": obs})
        return None
    finally:
        box.close()


# ---------------------------------------------------------------- execution of tests

RUNNER = r'''
import contextlib, importlib.util, io, json, os, signal, sys, traceback
sys.path.insert(0, os.getcwd())
res = {}
try:
    spec = importlib.util.spec_from_file_location("oracle", sys.argv[1])
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
except BaseException as e:
    print("@@" + json.dumps({"_load": "".join(traceback.format_exception_only(type(e), e)).strip()[-400:]})); sys.exit(0)
def alarm(*a): raise TimeoutError("case took over 20 s")
signal.signal(signal.SIGALRM, alarm)
for name in sorted(n for n in dir(m) if n.startswith("test_") and callable(getattr(m, n))):
    signal.alarm(20)
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            getattr(m, name)()
        res[name] = "ok"
    except BaseException as e:
        res[name] = "".join(traceback.format_exception(type(e), e, e.__traceback__, limit=-2))[-500:]
    finally:
        signal.alarm(0)
print("@@" + json.dumps(res))
'''


def evaluate(ws, oracles):
    """Run the project tests and every oracle file, each in a fresh copy of ws inside one sandbox."""
    os.makedirs(os.path.join(ws, ".agent", "oracles"), exist_ok=True)
    open(os.path.join(ws, ".agent", "runner.py"), "w").write(RUNNER)
    for k, src in oracles.items():
        open(os.path.join(ws, ".agent", "oracles", f"{k}.py"), "w").write(src)
    box = base.Sandbox(ws)
    fresh = "rm -rf /tmp/w && cp -a /work /tmp/w && cd /tmp/w && export PYTHONPATH=/tmp/w && "
    try:
        code, out, err = box.sh(fresh + "if [ -d tests ]; then python3 -m unittest discover -s tests 2>&1 | tail -25; exit ${PIPESTATUS[0]}; fi", timeout=180)
        res = {"tests_ok": code == 0, "tests_out": (out + err)[-1500:], "cases": {}}
        for k in oracles:
            code, out, err = box.sh(fresh + f"python3 .agent/runner.py .agent/oracles/{k}.py", timeout=240)
            line = next((l for l in out.splitlines()[::-1] if l.startswith("@@")), None)
            r = json.loads(line[2:]) if line else {"_load": "runner gave no result: " + (out + err)[-300:]}
            for name, v in r.items():
                res["cases"][f"{k}:{name}"] = v
        return res
    finally:
        box.close()


# ---------------------------------------------------------------- the graph

CODE_EXT = (".py", ".js", ".mjs", ".html", ".css", ".sql", ".bas", ".cls", ".vb", ".nft", ".sh", ".ini", ".toml", ".yaml", ".yml")

WEB_NOTE = ("\nThis container has Playwright for Python with headless Chromium (no network). Open local pages with "
            "p.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--allow-file-access-from-files']) "
            "and page.goto('file://' + os.path.abspath('index.html')); WebGL works. Use it to check pages, scripts and screenshots.")
CAD_NOTE = "\nThis container has CadQuery; read docs/CADTOOL.md for how to build and measure parts with /opt/cad/cadtool.py."

SYS = ("You are an expert software engineer. You work in a Linux container (Python 3.12, bash, no network); "
       "the project is in /work. Be exact: read the code and the docs before you conclude, and check every claim by running code.")


def run_task(task_text, workdir, profile, log):
    P = PROFILES[profile]
    TH = P["think"]
    t0 = time.time()
    root = os.path.dirname(workdir)
    gdir = os.path.join(root, "g")
    orig = copy_ws(workdir, os.path.join(gdir, "orig"))
    seed = {rel: open(os.path.join(orig, rel), "rb").read() for rel in files_of(orig)}

    # 1. recon: no model
    tree = outline(orig)
    base_eval = evaluate(copy_ws(orig, os.path.join(gdir, "probe")), {})
    log({"stage": "recon", "files": len(seed), "tests_ok": base_eval["tests_ok"]})

    # inputs the task does not ask to change are protected (one fast judgment per non-code file and provided test)
    cands = [p for p in seed if not p.endswith(".py") or p.startswith("tests/")]
    with cf.ThreadPoolExecutor(8) as ex:
        ps = list(ex.map(lambda p: judge(
            "Task given to an AI agent:\n<task>\n" + task_text[:3000] + "\n</task>\n"
            f"The file `{p}` is provided with the task. Does the task ask the agent to change, overwrite or fix the content "
            f"of `{p}` itself (not just read it, and not add new files next to it)? Answer modify=true only if so.", "modify"), cands))
    protected = {p for p, pr in zip(cands, ps) if pr < 0.5}
    log({"stage": "protect", "protected": sorted(protected)})

    # 2. requirements: structured, short
    docs = "\n\n".join(f"=== {rel} ===\n{read(orig, rel, 4000)}" for rel in files_of(orig)
                       if rel.lower().endswith((".md", ".txt", ".rst")) and rel.lower() != "license")[:12000]
    req = structured(
        f"Task:\n<task>\n{task_text}\n</task>\n\nProject files:\n{tree}\n\nDocs:\n{docs}\n\n"
        "List every concrete, checkable requirement: what the task asks to change, what must keep working, constraints "
        "(files that must not change), exact commands and output formats, AND every rule in the docs/spec that the "
        "behaviour depends on, including edge cases (boundaries such as >= vs >, ties and their order, empty input, "
        "rounding, error messages). One atomic rule per item, quoting exact values.",
        {"type": "object", "properties": {"requirements": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 24}},
         "required": ["requirements"]}, system=SYS)
    reqs = [r for r in req.get("requirements", []) if r.strip()][:24]
    req_text = "\n".join(f"R{i + 1}. {r}" for i, r in enumerate(reqs))
    log({"stage": "requirements", "reqs": reqs})

    image = base.sandbox_for(workdir)[0] or ""
    env_note = WEB_NOTE if "web" in image else CAD_NOTE if "cad" in image else ""
    head = (f"Task:\n<task>\n{task_text}\n</task>\n\nRequirements (from the task):\n{req_text}\n\nProject files:\n{tree}\n"
            + env_note + "\n")

    # 3. investigators: short read-only agents on separate copies, in parallel
    def investigate_(i):
        ws = copy_ws(orig, os.path.join(gdir, f"inv{i}"))
        return mini_agent(ws, SYS, head + "\nInvestigate only, do not fix yet: run the program or the exact commands from the task to "
                          "see the actual behaviour, read the relevant code, and find the root cause of every problem the task "
                          "describes (there may be more than one). Then call report.",
                          [T_BASH, T_READ, T_REPORT], "report", 10, "investigate" in TH, set(), log, f"inv{i}")
    def investigate(i):
        try:
            return investigate_(i)
        except Exception as e:
            log({"stage_error": f"inv{i}", "error": repr(e)[:300]}); return None
    with cf.ThreadPoolExecutor(P["investigators"]) as ex:
        reports = [r for r in ex.map(investigate, range(P["investigators"])) if r]
    diag = "\n\n".join(f"Investigator {i + 1}:\nObserved: {r.get('observed', '')}\nCause: {r.get('cause', '')}\nPlan: {r.get('fix_plan', '')}"
                       for i, r in enumerate(reports))[:9000]
    log({"stage": "investigate", "reports": reports})

    # source of the files the investigators point at (for the test writers)
    named = [rel for rel in files_of(orig) if rel.endswith(CODE_EXT) and not rel.startswith("tests/") and rel in diag
             and os.path.getsize(os.path.join(orig, rel)) < 60000][:6]
    srcs = "\n\n".join(f"=== {rel} ===\n{read(orig, rel, 8000)}" for rel in named)

    # 4. oracle tests: independent files; each case gets a validity weight from the fast judge
    def oracle(i):
        m = chat([{"role": "system", "content": SYS}, {"role": "user", "content":
                  head + f"\nFindings so far:\n{diag}\n\nRelevant source:\n{srcs}\n\n"
                  "Write ONE Python file of acceptance tests for this task, to be run with the current directory = the project root. "
                  "Define plain functions named test_r<N>_<what>() (N = requirement number) that use assert; one behaviour per "
                  "function; check exact values the task or docs give. Run commands with subprocess.run([sys.executable, '-m', ...], "
                  "capture_output=True, text=True) when the task names a command. Never modify provided files: copy what you need "
                  "into tempfile.mkdtemp() first. The tests describe the behaviour REQUIRED after the fix, so tests of the reported "
                  "problems are expected to fail on the current code. Output only the code in one ```python block."}],
                 temperature=0.8)
        return code_block(m.get("content"))
    with cf.ThreadPoolExecutor(P["oracles"]) as ex:
        oracles = {f"o{i}": src for i, src in enumerate(ex.map(oracle, range(P["oracles"]))) if "def test_" in src}

    # coverage: every requirement needs at least one test (test_r<N>_...); missing ones get a supplementary file
    covered = {int(n) for src in oracles.values() for n in re.findall(r"def test_r(\d+)", src)}
    missing = [i + 1 for i in range(len(reqs)) if i + 1 not in covered]
    log({"stage": "coverage", "missing": missing})
    if missing:
        def extra(j):
            part = missing[j::2]
            m = chat([{"role": "system", "content": SYS}, {"role": "user", "content":
                      head + f"\nFindings so far:\n{diag}\n\nRelevant source:\n{srcs}\n\n"
                      "Write ONE Python file of acceptance tests ONLY for these requirements: "
                      + ", ".join(f"R{n}" for n in part) + ". For each, define plain functions named test_r<N>_<what>() "
                      "that use assert and check the exact values/behaviour the requirement states (boundaries, ties, order, "
                      "errors). Run commands with subprocess.run([sys.executable, '-m', ...], capture_output=True, text=True) when "
                      "needed; copy provided files to tempfile.mkdtemp() before changing anything. The tests describe the REQUIRED "
                      "behaviour. Output only the code in one ```python block."}], temperature=0.7)
            return code_block(m.get("content")) if part else ""
        with cf.ThreadPoolExecutor(2) as ex:
            for j, src in enumerate(ex.map(extra, range(2))):
                if "def test_" in src:
                    oracles[f"x{j}"] = src
    orig_eval = evaluate(copy_ws(orig, os.path.join(gdir, "probe")), oracles)

    def case_src(key):
        k, name = key.split(":", 1)
        try:
            for n in ast.parse(oracles[k]).body:
                if isinstance(n, ast.FunctionDef) and n.name == name:
                    return ast.get_source_segment(oracles[k], n)
        except SyntaxError:
            pass
        return ""
    keys = [c for c in orig_eval["cases"] if not c.endswith(":_load")]
    with cf.ThreadPoolExecutor(8) as ex:
        ws_ = list(ex.map(lambda c: judge(
            "Task:\n<task>\n" + task_text[:3000] + "\n</task>\nRequirements:\n" + req_text + "\n\nA test written for this task:\n```python\n"
            + case_src(c)[:2500] + "\n```\nIs every expectation in this test (values, formats, behaviour) exactly what the task "
            "and requirements demand, with nothing invented or contradicting them? Answer valid=true only if so.", "valid"), keys))
    weight = dict(zip(keys, ws_))
    log({"stage": "oracles", "files": len(oracles), "cases": len(keys),
         "orig": {c: (orig_eval["cases"][c] == "ok", round(weight[c], 2)) for c in keys},
         "load_errors": {c: v for c, v in orig_eval["cases"].items() if c.endswith(":_load")}})

    code_files = [rel for rel in files_of(orig) if rel.endswith(CODE_EXT) and not rel.startswith("tests/")
                  and os.path.getsize(os.path.join(orig, rel)) < 60000]   # skip vendored libraries (three.module.js)
    focus = [rel for rel in code_files if rel in diag or rel in task_text or os.path.basename(rel) in task_text]
    if sum(len(read(orig, r)) for r in code_files) < 30000:
        focus = sorted(set(focus) | set(code_files), key=lambda r: (r not in focus, r))
    log({"stage": "focus", "files": focus})

    # 5. repair candidates: short agents on separate copies; each gets one oracle file as its target
    okeys = sorted(oracles)

    def repair(i, start=None, feedback=""):
        try:
            return repair_(i, start, feedback)
        except Exception as e:
            log({"stage_error": f"c{i}", "error": repr(e)[:300]})
            return os.path.join(gdir, f"c{i}"), ""

    def repair_(i, start=None, feedback=""):
        ws = copy_ws(start or orig, os.path.join(gdir, f"c{i}"))
        tgt = okeys[i % len(okeys)] if okeys else None
        extra = ""
        if tgt:
            os.makedirs(os.path.join(ws, ".agent"), exist_ok=True)
            open(os.path.join(ws, ".agent", "target_test.py"), "w").write(oracles[tgt])
            open(os.path.join(ws, ".agent", "runner.py"), "w").write(RUNNER)
            extra = ("\nAcceptance tests written from the task are in .agent/target_test.py; run them with "
                     "`python3 .agent/runner.py .agent/target_test.py` (prints each test as ok or its error). They may contain "
                     "mistakes: if a test contradicts the task or the docs, trust the task and ignore that test. Do not edit them.")
        rep = reports[i % len(reports)] if reports else None
        hint = (f"\nAn investigation found:\nObserved: {rep.get('observed', '')}\nCause: {rep.get('cause', '')}\nPlan: {rep.get('fix_plan', '')}\n"
                if rep else "")
        if start:
            hint = "\nYour previous attempt is already applied in /work. Its diff:\n" + base.clip(diff(orig, start), 4000) + "\n" + feedback
        code_now = listing(ws, focus)
        protect_note = ("\nThese provided files must not change: " + ", ".join(sorted(protected)) + ". Use /tmp for scratch files." if protected else "")
        before = start or orig
        args = mini_agent(ws, SYS, head + hint + extra + protect_note +
                          "\n\nCurrent content of the relevant files (line numbers are not part of the files). You already have "
                          "them, so do not read them again; read other files only if you need them:\n" + code_now +
                          "\n\nMake the change the task asks for in /work: edit the code with edit_file (old_text copied exactly, "
                          "without line numbers) or write_file. Fix the root cause, keep everything else working, then run the "
                          "project's tests (python3 -m unittest discover -s tests) and the task's commands, and call done.",
                          [T_BASH, T_READ, T_EDIT, T_WRITE, T_DONE], "done", 10 if start else 14,
                          ("refine" if start else "repair") in TH, protected, log, f"c{i}",
                          final_check=lambda: None if diff(before, ws) else
                          "[harness] Not accepted: no file has changed yet. Make the fix with edit_file or write_file first.")
        for p in protected:  # undo forbidden changes before judging
            fp = os.path.join(ws, p)
            if not os.path.exists(fp) or open(fp, "rb").read() != seed[p]:
                open(fp, "wb").write(seed[p])
        return ws, (args or {}).get("summary", "")

    def score_all(cands):
        evals = {}
        with cf.ThreadPoolExecutor(6) as ex:
            for ws, ev in zip(cands, ex.map(lambda w: evaluate(w, oracles), cands)):
                evals[ws] = ev
        # consensus: group candidates by the set of weighted cases they pass; group size x weighted passes
        vec = {ws: tuple(c for c in keys if ev["cases"].get(c) == "ok") for ws, ev in evals.items()}
        groups = {}
        for ws, v in vec.items():
            groups.setdefault((evals[ws]["tests_ok"], v), []).append(ws)
        def gscore(g):
            (tok, v), members = g
            return (tok, len(members) * sum(weight[c] for c in v) + sum(weight[c] for c in v) * 3)
        ranked = sorted(groups.items(), key=gscore, reverse=True)
        return evals, ranked

    with cf.ThreadPoolExecutor(P["candidates"]) as ex:
        first = list(ex.map(repair, range(P["candidates"])))
    cands = [ws for ws, _ in first if diff(orig, ws)]
    evals, ranked = score_all(cands) if cands else ({}, [])
    log({"stage": "candidates", "n": len(cands), "ranking": [(g[0][0], len(g[0][1]), [os.path.basename(w) for w in g[1]]) for g in ranked]})

    # 6. refine the leaders with what still fails (cases most other candidates pass, and the project tests)
    if ranked and P["refine"]:
        leaders = [g[1][0] for g in ranked[:2]]
        jobs = []
        for j, ws in enumerate(leaders):
            ev = evals[ws]
            fails = [c for c in keys if ev["cases"].get(c) != "ok" and weight[c] >= 0.5]
            fb = ""
            if not ev["tests_ok"]:
                fb += "The project's tests now FAIL:\n" + ev["tests_out"][-1200:] + "\n"
            if fails:
                fb += "These acceptance tests still fail (each may itself be wrong; check it against the task):\n" + "\n".join(
                    f"- {c}:\n{case_src(c)[:700]}\nerror: {ev['cases'].get(c, '')[-300:]}" for c in fails[:5]) + "\n"
            if not fb:
                fb = "All checks pass. Review the diff against every requirement and fix anything still missing; if nothing is missing, call done.\n"
            for r in range(P["refine"] // len(leaders)):
                jobs.append((len(first) + j * 10 + r, ws, fb))
        with cf.ThreadPoolExecutor(len(jobs)) as ex:
            more = list(ex.map(lambda a: repair(a[0], copy_ws(a[1], os.path.join(gdir, f"start{a[0]}")), a[2]), jobs))
        cands += [ws for ws, _ in more if diff(orig, ws)]
        evals, ranked = score_all(cands)
        log({"stage": "refine", "n": len(cands), "ranking": [(g[0][0], len(g[0][1]), [os.path.basename(w) for w in g[1]]) for g in ranked]})

    # 7. apply the winner to the real workspace
    win = ranked[0][1][0] if ranked else None
    if win:
        for rel in files_of(win):
            if rel in protected:
                continue
            src, dst = os.path.join(win, rel), os.path.join(workdir, rel)
            if read(win, rel) != read(workdir, rel):
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
        log({"stage": "apply", "winner": os.path.basename(win), "tests_ok": evals[win]["tests_ok"],
             "passed": sum(evals[win]["cases"].get(c) == "ok" for c in keys), "of": len(keys)})
    return {"steps": POOL.calls, "finished": bool(win), "seconds": round(time.time() - t0, 1)}
