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
import hashlib, json, os, re, shlex, time
import agent as base
import judge

KEEP_FULL = 5
CTX_SOFT_LIMIT = 40000  # characters; above this, old outputs are masked in one batch
MAX_STEPS = 30

SYSTEM_V6B_RULES = ("\n9. Never overwrite or edit the provided input/data files to test your code; put test data in /tmp. "
                    "Change only the files the task asks you to change or create.\n"
                    "10. If you notice a problem (a wrong count, a failing case), fix it and re-check before calling finish.")

SYSTEM_V6C_RULES = ("\n11. Test first: before implementing, write .agent/spec_test.py - a plain Python script with an assert for every "
                    "example, rule and edge case in the task (exact expected outputs, error types, exit codes, file contents). "
                    "Call the real functions/programs, not a wrapper that hides exceptions. Run it after each change. "
                    "The harness runs it again before accepting finish. Keep it there, not in the project files.")

SYSTEM_THINK_SHORT = " Keep each thought short (under about 100 words) and follow it with an action."

SYSTEM_DEBUG_RULES = """
Finding a bug whose cause is not obvious:
15. Reproduce it with the smallest input (one or two records) and work out the correct result by hand first.
16. Follow that input through every stage (for example parse -> store -> query -> aggregate -> output): print the
    value after each stage with a short python3 -c script. The first stage whose value differs from your hand
    result contains a bug; fix it there, not in a later stage.
17. Expect more than one bug. After each fix re-run all tests and repeat steps 15-16 for what still fails.
18. Usual suspects when code spans several modules: a cache whose key misses something that changes (stored data,
    a version counter, an argument) or that hands the same mutable object to every caller; a function that modifies
    the dict or list it was given; dates and times compared or grouped in different time zones (convert to one zone
    first); range ends off by one.
"""


SYSTEM_V7B_RULES = ("\n12. To move or split existing code, copy exact line ranges with a script (sed -n 'A,Bp' or Python slicing) "
                    "instead of retyping it from memory; then fix imports.\n"
                    "13. If the task says the output or behaviour must not change, first run the original version and save its output "
                    "under .agent/ (e.g. .agent/before.txt), and after every change compare with diff before going on.\n"
                    "14. After testing with test data, run the program again on the real input files of the task and show (cat) the final "
                    "output files to check them before calling finish. Final outputs must come from the real inputs.")

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


def _strip_comments(cmd):
    lines = [l for l in cmd.split("\n") if not l.strip().startswith("#")]
    return " ".join(" ".join(lines).split())


def akey(name, args, semantic=False):
    if semantic and name == "bash" and isinstance(args.get("command"), str):
        args = dict(args, command=_strip_comments(args["command"]))  # same command with different '# thoughts' = repeat
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


FEATURES = {
    "v5": set(),
    "v5b": {"incontext"},
    "v5c": {"repeat_result"},
    "v5d": {"repeat_result", "storm"},
    "v5e": {"repeat_result", "storm", "cache", "incontext"},
    "v5f": {"repeat_result", "storm", "cache", "incontext", "think"},
    "v6": {"repeat_result", "storm", "cache", "incontext", "think"},
    "v6b": {"repeat_result", "storm", "cache", "incontext", "think", "v6b"},
    "v6c": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec"},
    "v6d": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit"},
    "v6e": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs"},
    "v6f": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs"},
    "v7": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80"},
    "v7b": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules"},
    "v7d": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs"},
    "v7e": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act"},
    # v7f: empty, withheld or near-duplicate thoughts are not accepted (the model is shown its own plan and told to act);
    #      after 3+ steps of only refused repeats, the open todo items and a re-read of the task are pointed out
    "v7f": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "plan_lock"},
    # v7h: v7f with a 120-step budget
    "v7h": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps120",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "plan_lock"},
    # v7i: v7f with a debugging playbook (rules 15-18) and read-only originals in .agent/orig/; v7j: the same with 120 steps
    "v7i": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "plan_lock", "debug_rules", "keep_orig"},
    "v7j": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps120",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "plan_lock", "debug_rules", "keep_orig"},
    # v7g: v7e with a 120-step budget
    "v7g": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps120",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act"},
    "v7c": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation"},
}


def feats(profile):
    return FEATURES.get(profile, FEATURES.get(profile.rstrip("abcdefghijklmnopqrstuvwxyz-0123456789"), set()))


class State:
    def __init__(self):
        self.ran = {}            # action key -> (count, one-line result)
        self.full = {}           # action key -> full observation
        self.broken = 0          # consecutive cut-off tool calls
        self.changed = False     # did the last write/edit change a file?
        self.last_snap = None
        self.still = 0           # steps without any file change
        self.masked = set()
        self.v6b = False
        self.spec = False
        self.thinks = 0          # consecutive think calls
        self.thoughts = []       # accepted thoughts (v7f)
        self.refused = 0         # consecutive steps whose calls were all refused repeats
        self.recent = []         # last 8 steps: True = every call was a refused repeat
        self.compact = False     # the server reported a full context: keep the prompt at half the usual size
        self.think_limit = False
        self.restore = False
        self.restores = 0
        self.seed_bytes = {}
        self.judge_inputs = False
        self.allowed = set()
        self.protected = set()
        self.hard_tests = False
        self.test_gate_tries = 0
        self.read_window = False
        self.workdir = ""
        self.seed = {}      # message indexes whose output is shown elided (cache-friendly mode)
        self.todo = []
        self.edit_fail = {}
        self.finish_tries = 0
        self.judge_log = []
        self.hot = 0


def missing_args(tools, name, args):
    for t in tools:
        f = t["function"]
        if f["name"] == name:
            req = f["parameters"].get("required", [])
            miss = [r for r in req if r not in args or args[r] in (None, "")]
            if miss:
                props = f["parameters"]["properties"]
                return (f"error: {name} needs " + ", ".join(f"'{m}' ({props[m].get('type')})" for m in miss)
                        + f". Call {name} again with all of: {', '.join(req)}.")
    return None


def plan_lock(st, args, withheld):
    """v7f: refuse a thought that is empty, comes while think is withheld, or repeats an earlier one; return the
    refusal (None = accept). The model sees the plan it already made and is told to carry out its first step."""
    import difflib
    t = " ".join(str(args.get("thought", "")).split())
    prev = st.thoughts[-6:]
    dup = next((p for p in prev if t and difflib.SequenceMatcher(None, t[:400], p[:400]).ratio() > 0.75), None)
    if t and not withheld and dup is None:
        st.thoughts.append(t)
        return None
    st.thinks += 1
    plan = dup or (prev[-1] if prev else "")
    why = ("That thought is empty." if not t else "You already made this plan." if dup else "You have just thought twice in a row.")
    return (f"[harness] Not accepted: {why} Your plan so far: \"{plan[:500]}\" "
            "Do its first concrete step now with write_file, edit_file or bash (for example write the new function or "
            "section into the file). Do not plan again until you have changed a file and run a check.")


def run_tool(box, workdir, st, name, args):
    if name == "think":
        st.thinks += 1
        if st.think_limit and st.thinks >= 2:
            return "ok. [harness] You have thought twice in a row; now act (edit, run, or check something)."
        return "ok"
    if name == "todo":
        st.todo = [{"text": str(i.get("text", ""))[:200], "status": i.get("status", "pending")} for i in args.get("items", [])][:20]
        return "todo updated"
    if name == "read_file":
        path = str(args["path"]).strip()
        if path.startswith("/tmp/") and ".." not in path.split("/"):
            # scratch copies live in the sandbox's /tmp (v7f y_ledger_split moved the original there and could not read it back)
            code, out, err = box.sh(f"cat -- {shlex.quote(path)}")
            if code != 0:
                return f"error: {err.strip() or 'cannot read ' + path}"
            lines = out.split("\n")
        else:
            p = os.path.join(workdir, base.safe_path(path))
            with open(p, encoding="utf-8", errors="replace") as f:
                lines = f.read().split("\n")
        a, b = max(1, int(args.get("start") or 1)), min(len(lines), int(args.get("end") or len(lines)))
        if getattr(st, "read_window", False):
            # never cut the middle of a file: show a window that fits and say exactly how to read the rest
            shown, size = [], 0
            for i in range(a, b + 1):
                row = f"{i:4d}| {lines[i - 1]}"
                if size + len(row) > 20000 and shown:
                    return ("[line numbers and '| ' are added by the tool; they are not in the file]\n" + "\n".join(shown)
                            + f"\n[harness] Showing lines {a}-{i - 1} of {len(lines)}. Read the rest with read_file "
                            f"path={args['path']} start={i} end={min(len(lines), i + 300)}.")
                shown.append(row)
                size += len(row) + 1
            return ("[line numbers and '| ' are added by the tool; they are not in the file]\n" + ("\n".join(shown) or "(empty file)")
                    + (f"\n[lines {a}-{b} of {len(lines)}]" if b - a + 1 < len(lines) else ""))
        body = "\n".join(f"{i:4d}| {lines[i - 1]}" for i in range(a, b + 1))
        head = "[line numbers and '| ' are added by the tool; they are not in the file]\n" if st.v6b else ""
        return head + base.clip(body or "(empty file)") + (f"\n[{len(lines)} lines total]" if b - a + 1 < len(lines) else "")
    if name in ("write_file", "edit_file") and base.safe_path(args.get("path", "")) in getattr(st, "protected", set()):
        return (f"error: {args['path']} is a provided input file and the task does not ask you to change it, so it is read-only. "
                "Put test data in /tmp (e.g. /tmp/test_input) and point your program at it while testing.")
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


def elide_args(c):
    """Shorten an old call's long string arguments (file contents, edits), keeping valid JSON."""
    try:
        a = json.loads(c["function"]["arguments"] or "{}")
    except ValueError:
        return c
    if not isinstance(a, dict):
        return c
    # only file data is replaced; a command keeps its start, because the model copies whatever an old call looks like
    # (v7f h_md ran "[1982 chars, elided; ...]" as a bash command twice)
    def short(k, v):
        if not isinstance(v, str) or len(v) <= 300:
            return v
        if k == "command":
            return v[:300] + "\n# ... (rest of this earlier command not shown)"
        return f"[{len(v)} chars, elided; the file now holds the current version]"
    a = {k: short(k, v) for k, v in a.items()}
    return dict(c, function=dict(c["function"], arguments=json.dumps(a, ensure_ascii=False)))


def view(messages, st, cache_friendly=False):
    """Mask old observations; append the checklist as a transient last message.
    cache_friendly: never change what was already sent unless the context gets large; then mask a batch at once,
    so llama-server can keep reusing the cached prompt prefix between steps."""
    tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
    if cache_friendly:
        # written file contents count too: long runs overflowed the context through write_file arguments alone
        total = sum(len(m.get("content") or "") + sum(len(c["function"]["arguments"]) for c in m.get("tool_calls") or [])
                    for m in messages)
        limit = CTX_SOFT_LIMIT // (2 if st.compact else 1)
        if total > limit:
            calls_idx = [i for i, m in enumerate(messages) if m.get("tool_calls")]
            old_calls = set(calls_idx[:-KEEP_FULL])
            for i in sorted(set(tool_idx[:-KEEP_FULL]) | old_calls):
                if total <= limit // 2:
                    break
                if i in st.masked:
                    continue
                m = messages[i]
                size = len(m.get("content") or "") if m["role"] == "tool" else sum(len(c["function"]["arguments"]) for c in m["tool_calls"])
                if size > 200:
                    st.masked.add(i)
                    total -= size
        hide = st.masked
    else:
        hide = set(tool_idx[:-KEEP_FULL])
    out = []
    for i, m in enumerate(messages):
        if m["role"] == "tool" and i in hide and len(m["content"]) > 200:
            m = dict(m, content=f"[older output elided: {one_line(m['content'])}; {m['content'].count(chr(10)) + 1} lines]")
        elif m.get("tool_calls") and i in hide:
            m = dict(m, tool_calls=[elide_args(c) for c in m["tool_calls"]])
        out.append(m)
    tv = todo_view(st)
    if tv and out[-1]["role"] == "tool":
        out.append({"role": "user", "content": tv})
    return out


def snapshot(workdir, keep=None):
    """sha1 of every file; with keep={} also stores the bytes of files up to 2 MB (for restoring inputs)."""
    out = {}
    for root, _, files in os.walk(workdir):
        for f in files:
            p = os.path.join(root, f)
            try:
                b = open(p, "rb").read()
            except OSError:
                continue
            rel = os.path.relpath(p, workdir)
            out[rel] = hashlib.sha1(b).hexdigest()
            if keep is not None and len(b) <= 2_000_000:
                keep[rel] = b
    return out


def changed_inputs(workdir, seed, task):
    now = snapshot(workdir)
    changed = [p for p, h in seed.items() if now.get(p) != h]
    # files the task names are expected to change; others that changed are suspicious
    return [p for p in changed if os.path.basename(p) not in task and p not in task]


def protect_inputs(st, task, log):
    """Before the agent starts: provided non-code files the task does not ask to change become read-only."""
    st.protected = set()
    for p in sorted(st.seed_bytes):
        if p.endswith(".py") or p.startswith(".agent/"):
            continue
        q = ("Task given to an AI agent:\n<task>\n" + task[:2500] + "\n</task>\n"
             f"The file `{p}` is provided with the task. Does the task ask the agent to change, overwrite or fix "
             f"the content of `{p}` itself (not just read it as input)? Answer modify=true only if so.")
        val, pr, ms = judge.ask(q, "modify")
        st.judge_log.append(("protect:" + p, val, round(pr, 3), ms))
        if val is False:
            full = os.path.join(st.workdir, p)
            try:
                os.chmod(full, 0o444)
                st.protected.add(p)
            except OSError:
                pass
    if st.protected:
        log({"protected": sorted(st.protected)})


def keep_originals(st, log):
    """v7i: read-only copies of every provided file under .agent/orig/ (v7h y_ledger_split lost the original module
    after rewriting it and spent its last steps looking for the old content)."""
    n = 0
    for p, b in st.seed_bytes.items():
        if p.startswith(".agent/"):
            continue
        dst = os.path.join(st.workdir, ".agent", "orig", p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as f:
            f.write(b)
        os.chmod(dst, 0o444)
        n += 1
    log({"kept_originals": n})


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


def failing_tests(box):
    """Run the project's tests; return the failure report, or None when everything passes (or there are no tests)."""
    code, out, _ = box.sh("ls tests/test_*.py test_*.py 2>/dev/null | head -20")
    if not out.strip():
        return None
    reports = []
    if "tests/" in out:
        c, o, e = box.sh("python3 -m unittest discover -s tests 2>&1 | tail -40", timeout=120)
        if "FAILED" in o or ("Error" in o and not o.rstrip().endswith("OK")):
            reports.append(o.strip()[-2500:])
    for f in [x for x in out.split() if "/" not in x]:
        c, o, e = box.sh(f"python3 -m unittest {f[:-3]} 2>&1 | tail -30", timeout=120)
        if "FAILED" in o:
            reports.append(o.strip()[-1500:])
    return "\n\n".join(reports) or None


def on_finish(box, st, task, messages, args, in_context=False, cf=False, tools=None):
    if st.hard_tests and st.test_gate_tries < 4:
        rep = failing_tests(box)
        if rep:
            st.test_gate_tries += 1
            return ("[harness] Not accepted: the project's tests fail. Fix the code (do not edit existing tests unless the task "
                    "asks), re-run them, then call finish.\n" + rep)
    st.finish_tries += 1
    if st.finish_tries > 2:
        return None
    open_items = [i["text"] for i in st.todo if i["status"] not in ("done", "dropped")]
    checks = harness_checks(box)
    if st.restore:
        if st.judge_inputs:
            # decide per changed provided file with a fast boolean judgment instead of a filename heuristic
            now = snapshot(st.workdir)
            changed = [p for p, h in st.seed.items() if now.get(p) != h and p in st.seed_bytes and not p.endswith(".py")]
            sus = []
            for p in changed:
                if p in st.allowed:
                    continue
                q = ("Task given to an AI agent:\n<task>\n" + task[:2500] + "\n</task>\n"
                     f"The file `{p}` was provided with the task. Does the task ask the agent to change, overwrite or fix "
                     f"the content of `{p}` itself (not just read it as input)? Answer modify=true only if so.")
                val, pr, ms = judge.ask(q, "modify")
                st.judge_log.append(("modify:" + p, val, round(pr, 3), ms))
                if val is False:
                    sus.append(p)
                else:
                    st.allowed.add(p)
        else:
            sus = [p for p in changed_inputs(st.workdir, st.seed, task) if p in st.seed_bytes and not p.endswith(".py")]
        if sus and st.restores < 2:
            st.restores += 1
            for p in sus:
                with open(os.path.join(st.workdir, p), "wb") as f:
                    f.write(st.seed_bytes[p])
            return ("[harness] Not accepted: you modified provided input files the task did not ask you to change: " + ", ".join(sus)
                    + ". They have been restored to their original content. Never write test data into them (use /tmp). "
                    "Run your program again on the real files, check the output, then call finish.")
    if st.spec:
        code, out, err = box.sh("test -f .agent/spec_test.py || exit 99; python3 .agent/spec_test.py", timeout=60)
        if code == 99:
            if st.finish_tries == 1:
                return ("[harness] Not accepted yet: .agent/spec_test.py does not exist. Write it with an assert for every example, "
                        "rule and edge case in the task, run it, fix what fails, then call finish.")
        elif code != 0:
            return ("[harness] Not accepted: .agent/spec_test.py fails:\n" + base.clip((out + err).strip(), 1500)
                    + "\nFix the code (or the test if the test contradicts the task), run it again, then call finish.")
        else:
            checks += "\n.agent/spec_test.py: passed"
    if st.v6b:
        sus = changed_inputs(st.workdir, st.seed, task)
        if sus:
            checks += "\nWARNING: these provided files were modified although the task does not mention them: " + ", ".join(sus)
        thoughts = [m for m in messages if m["role"] == "assistant" for c in (m.get("tool_calls") or []) if c["function"]["name"] == "think"]
        notes = [json.loads(c["function"]["arguments"]).get("thought", "")[:300] for m in thoughts[-3:] for c in m["tool_calls"] if c["function"]["name"] == "think"]
        if notes:
            checks += "\nThe agent's own recent notes (check that every problem it noticed was fixed): " + " | ".join(notes)
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
    box = base.make_sandbox(workdir)
    st = State()
    st.v6b = "v6b" in feats(profile)
    st.spec = "spec" in feats(profile)
    st.think_limit = "think_limit" in feats(profile)
    st.workdir = workdir
    st.seed = snapshot(workdir, st.seed_bytes)
    st.restore = "restore_inputs" in feats(profile)
    st.hard_tests = "hard_tests" in feats(profile)
    st.read_window = "read_window" in feats(profile)
    if "protect_inputs" in feats(profile):
        protect_inputs(st, task_text, log)
    st.judge_inputs = "judge_inputs" in feats(profile)
    if "keep_orig" in feats(profile):
        keep_originals(st, log)
        task_text += ("\n\n[harness] Read-only copies of the files as they were given are in .agent/orig/ "
                      "(for example .agent/orig/" + (sorted(st.seed_bytes) or ["file"])[0] + "). Use them whenever you need the original code or data again.")
    t0 = time.time()
    F = feats(profile)
    think = "think" in F
    tools = TOOLS + [THINK_TOOL] if think else TOOLS
    messages = [{"role": "system", "content": SYSTEM + (SYSTEM_THINK_RULE + (SYSTEM_THINK_SHORT if "think_limit" in F else "") if think else "") + (SYSTEM_V6B_RULES if "v6b" in F else "") + (SYSTEM_V6C_RULES if "spec" in F else "") + (SYSTEM_V7B_RULES if "v7b_rules" in F else "") + (SYSTEM_DEBUG_RULES if "debug_rules" in F else "")},
                {"role": "user", "content": task_text}]
    finished, steps = False, 0
    try:
        max_steps = 120 if "steps120" in F else 80 if "steps80" in F else MAX_STEPS
        for steps in range(1, max_steps + 1):
            temp = 0.9 if st.hot else 0.3
            st.hot = max(0, st.hot - 1)
            v5d = "storm" in F
            cf = "cache" in F
            if v5d and st.broken:
                temp = 0.9  # the same prefix at low temperature reproduces the same runaway call
            try:
                ch = base.chat(view(messages, st, cf), [t for t in tools if t["function"]["name"] != "think"] if ("force_act" in F and st.thinks >= 2) else tools, max_tokens=(1536 if v5d and st.broken else 4096), temperature=temp)
            except base.ContextFull as e:
                log({"context_full": str(e)[:200]})
                if st.compact:
                    raise
                st.compact = True  # mask older calls and outputs down to half the soft limit, then retry this step
                continue
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
                    if not isinstance(a, dict):
                        a = None  # e.g. the model passed a bare number or string
                except ValueError:
                    a = None
                name = c["function"]["name"]
                sem = "semantic_repeat" in F
                skip = ("finish", "todo") if "force_act" in F else ("finish", "todo", "think")
                if a is not None and name not in skip and akey(name, a, sem) in st.ran:
                    n, res = st.ran[akey(name, a, sem)]
                    st.ran[akey(name, a, sem)] = (n + 1, res)
                    newer = "repeat_result" in F
                    full = st.full.get(akey(name, a, sem), res) if newer else res
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
            st.recent = (st.recent + [not fresh])[-8:]
            if not fresh:
                st.refused += 1
                extra = ""
                if "plan_lock" in F and (st.refused >= 3 or sum(st.recent) >= 5):
                    # consecutive, or interleaved with other commands (v7f h_md: 29 refused, never 3 in a row)
                    # v7f: a streak of refused repeats (e.g. writing the same file 40 times): point at the next open item
                    open_items = [i["text"] for i in st.todo if i.get("status") != "done"]
                    extra = (f" You keep repeating actions that already ran ({sum(st.recent)} of your last {len(st.recent)} steps). The files already contain what you wrote. "
                             + (f"Your unfinished todo items: {'; '.join(open_items[:5])}. Do the first one with a NEW action. " if open_items else "")
                             + "Re-read the task for anything not yet done (files to remove, outputs to produce, checks to run), "
                             "then do it; if all is done, run the checks once and call finish.")
                messages.append({"role": "user", "content": "[harness] " + " ".join(notes)
                                 + " Choose a different action that makes progress, or call finish if the task is done." + extra})
                continue
            if any(n not in ("todo", "think") for _, n, _ in fresh):
                st.refused = 0
            # never put unparsable arguments into the history: llama-server re-parses every past tool call and
            # one broken call there makes every later request fail with the same HTTP 500
            safe = []
            for c, _, a in fresh:
                if a is None:
                    c = dict(c, function=dict(c["function"], arguments=json.dumps({"_harness": "call was cut off or invalid JSON"})))
                safe.append(c)
            entry = {"role": "assistant", "content": m.get("content") or "", "tool_calls": safe}
            messages.append(entry)
            done_now = False
            for c, name, a in fresh:
                if name != "think":
                    st.thinks = 0
                if a is None:
                    obs = "error: arguments were not valid JSON. Call the tool again with valid JSON."
                elif name == "finish":
                    try:
                        r = on_finish(box, st, task_text, messages, a, in_context="incontext" in F, cf="cache" in F, tools=tools)
                    except Exception as e:  # a broken check must not kill the run; log it and accept
                        import traceback
                        log({"finish_check_error": traceback.format_exc()[-1200:]})
                        r = None
                    obs, done_now = ("finished", True) if r is None else (r, False)
                    if r:
                        log({"finish_rejected": r[:800]})
                else:
                    obs = missing_args(tools, name, a) if st.v6b else None
                    if obs is None and name == "think" and "plan_lock" in F:
                        obs = plan_lock(st, a, withheld=st.thinks >= 2)
                        if obs:
                            log({"plan_lock": obs[:200]})
                    if obs is None:
                        try:
                            obs = run_tool(box, workdir, st, name, a)
                        except Exception as e:
                            obs = f"error: {type(e).__name__}: {e}"
                    if name not in ("todo",) if "force_act" in F else name not in ("todo", "think"):
                        st.ran[akey(name, a, "semantic_repeat" in F)] = (1, one_line(obs))
                        st.full[akey(name, a, "semantic_repeat" in F)] = obs
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
            if "stagnation" in F:
                snap = snapshot(workdir)
                if "plan_lock" in F:  # rewriting its own spec test is not progress on the code (v7f h_md)
                    snap = {k: v for k, v in snap.items() if not k.startswith(".agent/")}
                if snap != st.last_snap:
                    st.last_snap, st.still = snap, 0
                else:
                    st.still += 1
                recent = " ".join(m["content"][-600:] for m in messages[-6:] if m["role"] == "tool")
                failing = any(w in recent for w in ("FAILED", "Traceback", "AssertionError", "Error:", "exit code: 1"))
                if st.still >= 10 and failing:
                    st.still = 0
                    st.hot = 1
                    messages.append({"role": "user", "content": "[harness] For 10 steps no file has changed while a check still fails. "
                                     "Stop probing with variations of the same command. Open the source code that the failing check "
                                     "exercises (read_file), find the actual cause, edit it, then re-run the check."})
                    log({"stagnation_nudge": True})
    finally:
        box.close()
    return {"steps": steps, "finished": finished, "seconds": round(time.time() - t0, 1), "judge": st.judge_log}
