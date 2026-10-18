"""Harness v5: research-driven loop (see docs/research-2026-10.md).

Differences from agent.py/v4:
- Repeated actions are never run or echoed verbatim; the model gets a harness-written description instead.
- Old failed calls stay in history but are rewritten as one-line descriptions (not deleted).
- A todo tool keeps the plan; its current state is shown as the last message every turn.
- Edits: cascading match (exact -> whitespace-tolerant with re-indent), py_compile check with rollback,
  whole-file rewrite suggested after 2 failed edits on one file.
- write_file has append mode, so big files can be written in parts.
- Observations older than the last KEEP_FULL tool results are masked to one line.
- On finish the harness itself compiles Python files, runs tests it can find, and gives the exit codes to a
  fast boolean judge; at most one fix-and-retry round.
"""
import hashlib, json, os, re, time
import agent as base
import judge

KEEP_FULL = 5
CTX_SOFT_LIMIT = 40000  # characters; above this, old outputs are masked in one batch
MAX_STEPS = 30

SYSTEM_THINK_RULE = ("\n8. When you need to reason (what the error means, what to check next, whether a requirement is met), "
                     "call the think tool. Never write reasoning as comments inside bash commands or files; keep commands short.")

SYSTEM = """You are an expert software engineer working as an autonomous agent in a Linux container (Python 3.12, bash, no network). The task files are in /work.

How to work:
1. First call todo with a short checklist of the task's requirements (exact file names, formats, edge cases).
2. Explore: list and read the relevant files before changing anything.
3. Make precise changes. Use edit_file for small changes; use write_file for new files (split big files: write the first part, then mode="append").
4. Verify each requirement with a command that shows the real result (run the program/tests, cat the output). Mark todo items done only after verifying.
5. If something fails, read the error, fix the cause, verify again.
6. Follow the task's exact names, formats and output wording. Do not modify tests unless asked.
7. When all todo items are done and verified, call finish with a short summary.

Tools: bash runs `bash -lc` in /work (60 s limit). read_file shows line numbers (do not copy them into edits)."""

THINK_TOOL = {"type": "function", "function": {"name": "think", "description": "Write down your reasoning or plan. It does not change anything. Use it instead of putting reasoning in commands, comments or files.",
    "parameters": {"type": "object", "properties": {"thought": {"type": "string"}}, "required": ["thought"]}}}

TOOLS = [
    base.TOOLS[0],
    {"type": "function", "function": {"name": "read_file", "description": "Read a text file (path relative to /work), with line numbers. Optional start/end line.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "start": {"type": "integer"}, "end": {"type": "integer"}}, "required": ["path"]}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a file. mode='overwrite' (default) replaces it; mode='append' adds to the end. Keep each call under about 150 lines.",
     "parameters": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}, "mode": {"type": "string", "enum": ["overwrite", "append"]}}, "required": ["path", "content"]}}},
    base.TOOLS[3],
    {"type": "function", "function": {"name": "todo", "description": "Set the task checklist. Pass the full list each time with each item's status.",
     "parameters": {"type": "object", "properties": {"items": {"type": "array", "items": {"type": "object", "properties": {
         "text": {"type": "string"}, "status": {"type": "string", "enum": ["pending", "in_progress", "done", "dropped"]}}, "required": ["text", "status"]}}},
         "required": ["items"]}}},
    base.TOOLS[4],
]


def akey(name, args):
    return hashlib.sha1((name + json.dumps(args, sort_keys=True, ensure_ascii=False)).encode()).hexdigest()


def describe(name, args):
    if name == "bash":
        c = args.get("command", "").strip().split("\n")[0]
        return f"bash `{c[:60]}{'...' if len(c) > 60 else ''}`"
    if name in ("read_file", "write_file", "edit_file"):
        return f"{name} {args.get('path', '')}"
    return name


def one_line(obs):
    lines = [l for l in obs.strip().split("\n") if l.strip() and not l.startswith("---") and not l.startswith("exit code")]
    code = re.search(r"exit code: (\d+)", obs)
    # for failures the useful line is the last one (the exception), not "Traceback (most recent call last):"
    pick = lines[-1] if (code and code.group(1) != "0" and lines) else (lines[0] if lines else "(no output)")
    return (f"exit {code.group(1)}, " if code else "") + pick.strip()[:160]


def py_check(box, path):
    if not path.endswith(".py"):
        return None
    code, out, err = box.sh(f"python3 -m py_compile {json.dumps(path)}", timeout=20)
    return None if code == 0 else (err or out).strip()[-800:]


class State:
    def __init__(self):
        self.ran = {}            # action key -> (count, one-line result)
        self.full = {}           # action key -> full observation
        self.broken = 0          # consecutive cut-off tool calls
        self.changed = False     # did the last write/edit change a file?
        self.masked = set()      # message indexes whose output is shown elided (cache-friendly mode)
        self.todo = []
        self.edit_fail = {}
        self.finish_tries = 0
        self.judge_log = []
        self.hot = 0


def run_tool(box, workdir, st, name, args):
    if name == "think":
        return "ok"
    if name == "todo":
        st.todo = [{"text": str(i.get("text", ""))[:200], "status": i.get("status", "pending")} for i in args.get("items", [])][:20]
        return "todo updated"
    if name == "read_file":
        p = os.path.join(workdir, base.safe_path(args["path"]))
        with open(p, encoding="utf-8", errors="replace") as f:
            lines = f.read().split("\n")
        a, b = max(1, int(args.get("start") or 1)), min(len(lines), int(args.get("end") or len(lines)))
        body = "\n".join(f"{i:4d}| {lines[i - 1]}" for i in range(a, b + 1))
        return base.clip(body or "(empty file)") + (f"\n[{len(lines)} lines total]" if b - a + 1 < len(lines) else "")
    if name == "write_file":
        rel = base.safe_path(args["path"])
        p = os.path.join(workdir, rel)
        os.makedirs(os.path.dirname(p) or workdir, exist_ok=True)
        mode = "a" if args.get("mode") == "append" else "w"
        prev = open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None
        st.changed = mode == "a" or prev != args["content"]
        with open(p, mode, encoding="utf-8") as f:
            f.write(args["content"])
        msg = f"{'appended' if mode == 'a' else 'wrote'} {len(args['content'])} chars to {rel}"
        err = py_check(box, rel)
        return msg + (f"\nwarning: {rel} does not compile yet:\n{err}" if err else "")
    if name == "edit_file":
        rel = base.safe_path(args["path"])
        p = os.path.join(workdir, rel)
        with open(p, encoding="utf-8") as f:
            before = f.read()
        old, new = args["old_text"], args["new_text"]
        if old == new:
            return "error: old_text and new_text are identical, so nothing changed. Decide what the code should become and put that in new_text."
        n = before.count(old)
        after = before.replace(old, new) if n == 1 else (base.fuzzy_replace(before, old, new) if n == 0 else None)
        if after is None:
            st.edit_fail[rel] = st.edit_fail.get(rel, 0) + 1
            hint = (f"error: old_text found {n} times (must be exactly 1); include more surrounding lines." if n > 1
                    else "error: old_text not found. " + base.closest_lines(before, old))
            if st.edit_fail[rel] >= 2:
                hint += f"\n[harness] Editing {rel} failed {st.edit_fail[rel]} times. Rewrite the whole file with write_file instead."
            return hint
        st.changed = after != before
        with open(p, "w", encoding="utf-8") as f:
            f.write(after)
        err = py_check(box, rel)
        if err:
            with open(p, "w", encoding="utf-8") as f:
                f.write(before)
            return f"error: the edit made {rel} invalid Python, so it was rolled back:\n{err}"
        st.edit_fail[rel] = 0
        return "edited"
    return base.run_tool(box, workdir, name, args)


def todo_view(st):
    if not st.todo:
        return None
    mark = {"pending": "[ ]", "in_progress": "[~]", "done": "[x]", "dropped": "[-]"}
    return "[harness] Current checklist:\n" + "\n".join(f"{mark.get(i['status'], '[ ]')} {i['text']}" for i in st.todo)


def view(messages, st, cache_friendly=False):
    """Mask old observations; append the checklist as a transient last message.
    cache_friendly: never change what was already sent unless the context gets large; then mask a batch at once,
    so llama-server can keep reusing the cached prompt prefix between steps."""
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    if cache_friendly:
        total = sum(len(m.get("content") or "") for m in messages)
        if total > CTX_SOFT_LIMIT:
            for i in tool_idx[:-KEEP_FULL]:
                if total <= CTX_SOFT_LIMIT // 2:
                    break
                if i not in st.masked and len(messages[i]["content"]) > 200:
                    st.masked.add(i)
                    total -= len(messages[i]["content"])
        hide = st.masked
    else:
        hide = set(tool_idx[:-KEEP_FULL])
    out = []
    for i, m in enumerate(messages):
        if m["role"] == "tool" and i in hide and len(m["content"]) > 200:
            m = dict(m, content=f"[older output elided: {one_line(m['content'])}; {m['content'].count(chr(10)) + 1} lines]")
        out.append(m)
    tv = todo_view(st)
    if tv and out[-1]["role"] == "tool":
        out.append({"role": "user", "content": tv})
    return out


def harness_checks(box):
    """Run what the harness can verify by itself: compile all .py files, run unittest/test files if present."""
    lines = []
    code, out, err = box.sh("python3 -m compileall -q . >/dev/null 2>/tmp/ce; c=$?; tail -c 600 /tmp/ce; exit $c", timeout=30)
    lines.append(f"compile all python files: exit {code}" + (f" ({(out + err).strip()[-300:]})" if code else ""))
    code, out, _ = box.sh("ls test_*.py tests/test_*.py 2>/dev/null | head -5")
    if out.strip():
        c2, o2, e2 = box.sh("python3 -m unittest discover -s tests -q 2>&1 | tail -3; for f in test_*.py; do [ -f \"$f\" ] && python3 \"$f\" 2>&1 | tail -2; done", timeout=60)
        lines.append(f"tests found ({' '.join(out.split())}): output tail: {(o2 + e2).strip()[-400:]}")
    return "\n".join(lines)


def on_finish(box, st, task, messages, args, in_context=False, cf=False, tools=None):
    st.finish_tries += 1
    if st.finish_tries > 2:
        return None
    open_items = [i["text"] for i in st.todo if i["status"] not in ("done", "dropped")]
    checks = harness_checks(box)
    q = ("You check an AI agent's work. Task:\n<task>\n" + task[:2500] + "\n</task>\nRecent actions and results:\n<log>\n"
         + judge.evidence(messages) + "\n</log>\nAutomatic checks run by the harness just now:\n" + checks
         + ("\nUnfinished checklist items: " + "; ".join(open_items) if open_items else "")
         + "\nAgent's summary: " + str(args.get("summary", ""))[:400]
         + "\n\nIs every requirement of the task met, with evidence that the final result is correct? Answer done=true only if so.")
    if in_context:
        q2 = ("Automatic checks run by the harness just now:\n" + checks
              + ("\nUnfinished checklist items: " + "; ".join(open_items) if open_items else "")
              + "\nIs every requirement of the original task met, with evidence in this conversation that the final result is correct? "
              "Answer done=true only if so.")
        val, p, ms = judge.ask_in_context(view(messages, st, cf), tools or TOOLS, q2, "done")
    else:
        val, p, ms = judge.ask(q, "done")
    st.judge_log.append(("finish", val, round(p, 3), ms))
    if val is False and p >= 0.6:
        return ("[harness] Not accepted yet. Automatic checks:\n" + checks
                + ("\nUnfinished checklist items: " + "; ".join(open_items) if open_items else "")
                + "\nFind what is still missing or wrong, fix it, verify, then call finish.")
    return None


def run_task(task_text, workdir, profile, log):
    box = base.Sandbox(workdir)
    st = State()
    t0 = time.time()
    think = profile.startswith("v5f")
    tools = TOOLS + [THINK_TOOL] if think else TOOLS
    messages = [{"role": "system", "content": SYSTEM + (SYSTEM_THINK_RULE if think else "")}, {"role": "user", "content": task_text}]
    finished, steps = False, 0
    try:
        for steps in range(1, MAX_STEPS + 1):
            temp = 0.9 if st.hot else 0.3
            st.hot = max(0, st.hot - 1)
            v5d = profile.startswith(("v5d", "v5e", "v5f"))
            cf = profile.startswith(("v5e", "v5f"))
            if v5d and st.broken:
                temp = 0.9  # the same prefix at low temperature reproduces the same runaway call
            try:
                ch = base.chat(view(messages, st, cf), tools, max_tokens=(1536 if v5d and st.broken else 4096), temperature=temp)
            except base.BrokenToolCall as e:
                log({"broken_tool_call": str(e)[:300]})
                st.broken += 1
                msg = ("[harness] Your last tool call was cut off or invalid JSON, so nothing ran. "
                       "Write big files in parts (write_file, then mode=\"append\") and keep each call short.")
                if v5d:
                    msg = ("[harness] Your last tool call was cut off (it grew past the length limit), so nothing ran. "
                           "Do not write your reasoning as comments inside code or commands. Make the call short: "
                           "at most about 60 lines of content per write_file; continue with mode=\"append\".")
                    if messages[-1]["role"] == "user" and messages[-1]["content"].startswith("[harness] Your last tool call was cut off"):
                        continue  # do not stack the same warning
                messages.append({"role": "user", "content": msg})
                continue
            st.broken = 0
            m = ch["message"]
            calls = m.get("tool_calls") or []
            log({"step": steps, "content": (m.get("content") or "")[:2000], "calls": [(c["function"]["name"], c["function"]["arguments"][:1500]) for c in calls]})
            if not calls:
                messages.append({"role": "assistant", "content": m.get("content") or ""})
                messages.append({"role": "user", "content": "[harness] Continue with the tools. If everything is done and verified, call finish."})
                continue
            # repeated actions: do not run, do not echo the call; describe it instead
            fresh, notes = [], []
            for c in calls:
                try:
                    a = json.loads(c["function"]["arguments"] or "{}")
                except ValueError:
                    a = None
                name = c["function"]["name"]
                if a is not None and name not in ("finish", "todo", "think") and akey(name, a) in st.ran:
                    n, res = st.ran[akey(name, a)]
                    st.ran[akey(name, a)] = (n + 1, res)
                    newer = profile.startswith(("v5c", "v5d", "v5e", "v5f"))
                    full = st.full.get(akey(name, a), res) if newer else res
                    if newer:
                        notes.append(f"{describe(name, a)} already ran {n} time(s) and nothing has changed since, so it was not run again. "
                                     f"Its result was:\n{base.clip(full, 2500)}")
                    else:
                        notes.append(f"{describe(name, a)} was already run {n} time(s) with result: {res}. It was not run again.")
                else:
                    fresh.append((c, name, a))
            if notes:
                st.hot = 1
                log({"repeat_described": notes})
            if not fresh:
                messages.append({"role": "user", "content": "[harness] " + " ".join(notes)
                                 + " Choose a different action that makes progress, or call finish if the task is done."})
                continue
            entry = {"role": "assistant", "content": m.get("content") or "", "tool_calls": [c for c, _, _ in fresh]}
            messages.append(entry)
            done_now = False
            for c, name, a in fresh:
                if a is None:
                    obs = "error: arguments were not valid JSON. Call the tool again with valid JSON."
                elif name == "finish":
                    r = on_finish(box, st, task_text, messages, a, in_context=profile.startswith(("v5b", "v5e", "v5f")), cf=profile.startswith(("v5e", "v5f")), tools=tools)
                    obs, done_now = ("finished", True) if r is None else (r, False)
                    if r:
                        log({"finish_rejected": r[:800]})
                else:
                    try:
                        obs = run_tool(box, workdir, st, name, a)
                    except Exception as e:
                        obs = f"error: {e}"
                    if name not in ("todo", "think"):
                        st.ran[akey(name, a)] = (1, one_line(obs))
                        st.full[akey(name, a)] = obs
                        # a later change can make an earlier command worth re-running
                        if name in ("write_file", "edit_file") and not obs.startswith("error") and st.changed:
                            st.ran, st.full = {}, {}  # files changed: every earlier command may give a new result
                if notes:
                    obs += "\n[harness] " + " ".join(notes)
                    notes = []
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": obs})
                log({"obs": obs[:1500]})
            if done_now:
                finished = True
                break
    finally:
        box.close()
    return {"steps": steps, "finished": finished, "seconds": round(time.time() - t0, 1), "judge": st.judge_log}
