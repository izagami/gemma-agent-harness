#!/usr/bin/env python3
"""Facts about a finished result, collected by the harness with no model involved (2026-10-23).

The 26B cannot be trusted to write checks or expected values (v7z: ~50% of its checks flagged correct solutions),
but a fast boolean judgment over facts the harness gathered itself is accurate. So this module only gathers:
the commands written in the task (run as written), test results, output files as raw bytes with line-end/BOM/
encoding facts, comparisons with provided expected-output files, and for web pages what Chromium shows.
"""
import hashlib, json, os, re, shlex, shutil, time

import agent as base
from concurrent.futures import ThreadPoolExecutor

FRESH = "rm -rf /tmp/w && cp -a /work /tmp/w && cd /tmp/w && export PYTHONPATH=/tmp/w && "
SKIP = {".git", "__pycache__", ".agent", ".cache", "node_modules"}
TEXT_OUT = (".csv", ".txt", ".tsv", ".json", ".out", ".log", ".md", ".xml", ".html", ".sql", ".nft", ".conf", ".ini")
CMD_START = ("python3 ", "python ", "bash ", "sh ", "sqlite3 ", "node ", "nft ")


def files(root):
    out = {}
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP]
        for fn in fns:
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            try:
                out[rel] = hashlib.sha1(open(p, "rb").read()).hexdigest()
            except OSError:
                pass
    return out


PLACEHOLDER_EXT = {"DB": (".db", ".sqlite", ".sqlite3"), "CSV": (".csv",), "JSON": (".json",), "JSONL": (".jsonl",),
                   "TXT": (".txt",), "FILE": None, "INPUT": None, "PATH": None}


def generators(root, provided):
    """provided scripts that say in their first docstring line how to make a sample input, e.g. q_db_migrate's
    data/make_v1.py: "Create a sample v1 database: python3 data/make_v1.py PATH" -> {"DB": "python3 data/make_v1.py {out}"}"""
    out = {}
    for p in sorted(provided):
        if not p.endswith(".py") or p.startswith("tests/"):
            continue
        try:
            head = open(os.path.join(root, p), errors="replace").read(600)
        except OSError:
            continue
        m = re.search(r'"""([^\n]*?)python3 (\S+) ([A-Z_]+)', head)
        if not m or m.group(2) != p:
            continue
        kind = "DB" if re.search(r"database|sqlite|\bdb\b", m.group(1), re.I) else "CSV" if re.search(r"csv", m.group(1), re.I) else None
        if kind and kind not in out:
            out[kind] = f"python3 {p} {{out}}"
    return out


def task_commands(task, provided=(), gens=None):
    """commands quoted in the task text. A placeholder such as DB or CSV is filled with a provided file of that kind
    (q25 db_migrate: `python3 -m crm.migrate DB` was skipped, so the migration itself was never run)"""
    data = sorted(p for p in provided if p.startswith(("data/", "samples/", "fixtures/")))
    cmds = []
    for c in re.findall(r"`([^`\n]{4,200})`", task):
        c = c.strip()
        if not c.startswith(CMD_START):
            continue
        args, ok = c.split(), True
        for i, a in enumerate(args[1:], 1):
            if re.fullmatch(r"<[^>]+>|\.\.\.|\[.*\]", a):
                ok = False
            elif re.fullmatch(r"[A-Z][A-Z_]+", a) and a in PLACEHOLDER_EXT:
                ext = PLACEHOLDER_EXT[a]
                hit = [p for p in data if ext is None or p.lower().endswith(ext)]
                if hit:
                    args[i] = hit[0]
                elif gens and a in gens:   # made by a provided generator first (see generators())
                    out = f"sample_{a.lower()}" + (ext[0] if ext else "")   # inside the run copy, so its content is collected
                    args[i] = out
                    prep = gens[a].format(out=out)
                    if prep not in cmds:
                        cmds.append(prep)
                else:
                    ok = False
            elif re.fullmatch(r"[A-Z][A-Z_]+", a):
                ok = False
        c = " ".join(args)
        if ok and c not in cmds:
            cmds.append(c)
    return cmds[:6]


def setup(ws, task):
    """how to start what the task's commands need (a provided server, environment variables), taken from the task and
    the docs. The model only proposes; a command is used only if it appears verbatim in the docs/task, and an env value
    only if that value is written there (browser_fix 10-23: run without server options and login, the script just timed out)."""
    import agent_g as G
    docs = task + "\n" + "\n".join(open(os.path.join(dp, f), errors="replace").read()[:6000]
                                    for dp, _, fs in os.walk(os.path.join(ws, "docs")) for f in fs if f.endswith((".md", ".txt")))
    if not re.search(r"server|サーバ|環境変数|environment variable", docs, re.I):
        return "", {}
    d = G.structured("Documents of a project:\n<docs>\n" + docs[:9000] + "\n</docs>\n\nTo run the commands the task "
                     "names, what must run in the background (for example a provided test server, with the exact options the "
                     "docs give), and which environment variables must be set to which values the docs give (URL, user, "
                     "password)? Use only commands and values written in the documents.",
                     {"type": "object", "properties": {"background": {"type": "array", "items": {"type": "string"}, "maxItems": 2},
                      "env": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "value": {"type": "string"}},
                              "required": ["name", "value"]}, "maxItems": 6}}, "required": ["background", "env"]})
    bg = [c.strip().rstrip("&").strip() for c in d.get("background", []) if c.strip().rstrip("&").strip() in docs][:2]
    env = {e["name"]: e["value"] for e in d.get("env", []) if re.fullmatch(r"[A-Z_][A-Z0-9_]*", e.get("name", ""))
           and e["name"] in docs and e.get("value") and e["value"] in docs}
    if not bg or not env:  # a URL value may be written as host:port in the docs; accept it only when grounded too
        pass
    return "".join(f"({c} >/tmp/server.log 2>&1 &) ; " for c in bg) + ("sleep 2; " if bg else ""), env


def byte_facts(path, head=500):
    b = open(path, "rb").read()
    if len(b) <= 3500:
        head = len(b)   # small files whole: a cut file made the judge read "not shown" as "missing" (10-23 firewall)
    crlf, lf = b.count(b"\r\n"), b.count(b"\n")
    enc = "utf-8"
    try:
        b.decode("utf-8")
    except UnicodeDecodeError:
        try:
            b.decode("cp932"); enc = "cp932 (not valid UTF-8)"
        except UnicodeDecodeError:
            enc = "neither UTF-8 nor cp932"
    def show(x):  # decoded so Japanese stays readable for the judge; repr keeps \r \n \t visible
        for e in ("utf-8", "cp932"):
            try:
                return repr(x.decode(e))
            except UnicodeDecodeError:
                pass
        return repr(x)
    return (f"{len(b)} bytes, encoding {enc}, BOM {'yes' if b.startswith(b'\xef\xbb\xbf') else 'no'}, "
            f"line ends: {crlf} CRLF, {lf - crlf} LF-only" + (f", {b.count(b'\r') - crlf} CR not followed by LF (e.g. \\r\\r\\n)" if b.count(b"\r") > crlf and os.environ.get("EV_DIFFLINE") == "1" else "") + f", ends with newline: {b.endswith(b'\n')}\n"
            f"content (Python repr): {show(b[:head])}" + (f"\nend: {show(b[-200:])}" if len(b) > head + 200 else ""))


def first_diff(exp_path, got_path, e, p):
    """the first differing line of two outputs, decoded, with \\r \\n \\t visible (v7w: a bare DIFFERENT left the model
    hunting through hex dumps for 60 steps, 10-23 vba_text)"""
    a, b = open(exp_path, "rb").read(), open(got_path, "rb").read()
    la, lb = (re.findall(rb"[^\n]*\n|[^\n]+$", x) for x in (a, b))   # split at \n only: a stray \r stays visible
    def show(x):
        for enc in ("utf-8", "cp932"):
            try:
                return repr(x.decode(enc))
            except UnicodeDecodeError:
                pass
        return repr(x)
    for i in range(max(len(la), len(lb))):
        x = la[i] if i < len(la) else b""
        y = lb[i] if i < len(lb) else b""
        if x != y:
            k = next((j for j in range(min(len(x), len(y))) if x[j] != y[j]), min(len(x), len(y)))
            return (f"First differing line: line {i + 1} ({len(la)} lines in {e}, {len(lb)} in {p}; first different byte at "
                    f"column {k + 1} of that line)\n  {e}: " + (show(x) if x else "(no such line)")
                    + f"\n  {p}: " + (show(y) if y else "(no such line)"))
    return "No line differs, yet the bytes do"


WEB_PROBE = r'''
import json, os, sys
from playwright.sync_api import sync_playwright
out = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--allow-file-access-from-files"])
    for f in sys.argv[1:]:
        pg = b.new_page(); errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        try:
            pg.goto("file://" + os.path.abspath(f)); pg.wait_for_timeout(1500)
            ids = pg.eval_on_selector_all("[id]", "els => els.map(e => e.tagName.toLowerCase() + '#' + e.id)")
            text = pg.inner_text("body")[:1200]
        except Exception as e:
            ids, text = [], "error: " + str(e)[:300]
        out[f] = {"console_errors": errs[:8], "ids": ids[:80], "text": text}
    b.close()
print("@@" + json.dumps(out, ensure_ascii=False))
'''


DOCEX = {}   # seed_dir -> cases (the docs do not change during a task)


def doc_blocks(docs):
    """example candidates cut out by the harness, not found by the model: fenced and indented blocks with the text
    just before them (the first EV_DOCEX try let the 26B scan whole docs: it made up outputs and wrote no input files)"""
    out, lines = [], docs.splitlines()
    i = 0
    while i < len(lines):
        l = lines[i]
        if l.strip().startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                j += 1
            blk, end = "\n".join(lines[i + 1:j]), j + 1
        elif l.startswith(("    ", "\t")) and l.strip():
            j = i
            while j < len(lines) and (lines[j].startswith(("    ", "\t")) or not lines[j].strip()):
                j += 1
            blk, end = "\n".join(lines[i:j]).rstrip(), j
        else:
            i += 1
            continue
        if blk.strip():
            ctx = "\n".join(lines[max(0, i - 8):i])
            out.append((ctx, blk))
        i = end
    return out[:10]


def doc_examples(seed_dir, task):
    """EV_DOCEX=1: worked examples the docs state literally, as runnable cases. The harness cuts the example blocks out
    of the docs; the 26B turns one block at a time into input files + command + expected output, copied from the block
    (never derived); Jev keeps only cases whose expectation the docs state. 10-24: toposort's SPEC.md shows an order
    example and a cycle example; the harness never ran them and the hidden check passed 29 of 54 cases."""
    if seed_dir in DOCEX:
        return DOCEX[seed_dir]
    import agent_g as G
    docs = docs_text(seed_dir)[:12000]
    cmds = [c for c in re.findall(r"`([^`\n]{4,200})`", task + "\n" + docs) if c.strip().startswith(CMD_START)][:6]
    schema = {"type": "object", "required": ["is_example", "files", "command", "stdout", "stderr", "exit"], "properties": {
        "is_example": {"type": "boolean"},
        "files": {"type": "array", "maxItems": 3, "items": {"type": "object", "required": ["path", "content"], "properties": {
            "path": {"type": "string", "maxLength": 80}, "content": {"type": "string", "maxLength": 1500}}}},
        "command": {"type": "string", "maxLength": 300}, "stdout": {"type": "string", "maxLength": 1500},
        "stderr": {"type": "string", "maxLength": 400}, "exit": {"type": "integer"}}}
    def one(cb):
        ctx, blk = cb
        c = G.structured_safe(G.structured,
            f"Commands the task names:\n" + "\n".join(cmds) + f"\n\nA passage of the docs:\n<<<\n{ctx}\n{blk}\n>>>\n\n"
            "Is the indented/fenced block a worked example: an input together with the output (or error and exit code) the "
            "docs give for it? If yes: files = the input files to create (path relative to the project, content copied "
            "exactly from the example), command = the task's command run on them, stdout / stderr / exit = exactly what the "
            "example shows (empty string or -1 where it shows nothing). Copy, never work out an output. If the block is not "
            "such an example (a format description, a code sample, a rule), is_example = false.", schema, False, G.SYS)
        if not c or not c.get("is_example") or not c.get("command") or not (c.get("stdout") or c.get("stderr")):
            return None
        exp = f"stdout {c['stdout']!r}, stderr {c['stderr']!r}, exit code {c['exit']}"
        inp = "\n".join(f"--- {f['path']} ---\n{f['content']}" for f in c["files"])
        p = G.judge(f"A passage of the docs:\n<<<\n{ctx}\n{blk}\n>>>\n\nA test case made from it:\ninput files:\n{inp}\n$ {c['command']}\n"
                    f"expected: {exp}\n\nAre this input and this expected output exactly what the passage shows (nothing "
                    "added, nothing worked out)?", key="faithful")
        return c if p >= 0.8 else None
    with ThreadPoolExecutor(4) as ex:
        cases = [c for c in ex.map(one, doc_blocks(docs)) if c]
    DOCEX[seed_dir] = cases
    return cases


def run_doc_examples(box, seed_dir, task, start=""):
    out = []
    for i, c in enumerate(doc_examples(seed_dir, task), 1):
        setup = "".join(f"mkdir -p \"$(dirname {shlex.quote(f['path'])})\"; cat > {shlex.quote(f['path'])} <<'DOCEX_EOF'\n{f['content']}\nDOCEX_EOF\n"
                        for f in c["files"])
        code, so, se = box.sh(FRESH + start + "\n" + setup + c["command"], timeout=60)
        checks = [("stdout", c["stdout"], so), ("stderr", c["stderr"], se)]
        diffs = [f"{k} expected {e!r}, got {g!r}" for k, e, g in checks if e and e.strip() != g.strip()]
        if c["exit"] >= 0 and code != c["exit"]:
            diffs.append(f"exit code expected {c['exit']}, got {code}")
        out.append((f"Docs example {i} ($ {c['command']}): " + ("matches the docs" if not diffs else "DIFFERS from the docs: "
                    + "; ".join(diffs))).replace("\n", "\\n")[:1200])   # one line, so the gate can read it
    return out


PROBE_PROMPT = (
    "Below are a programming task and part of its project documentation. Write up to {n} shell commands, each of which "
    "exercises ONE specific rule stated in the text below on a small concrete input, so that a reader of its output can "
    "see whether a finished program follows that rule. Prefer rules about edge cases, exact output format, error "
    "messages, exit codes and boundary values.\n"
    "- Each command runs with bash in a fresh copy of the project as the current directory (files: {files}). Use the "
    "project's own command line or functions as the documentation describes them (e.g. python3 -m pkg ARGS, or "
    "python3 -c 'from pkg.mod import f; print(repr(f(...)))').\n"
    "- Create any input you need inside the command (printf ... > /tmp/p1.csv, or a heredoc), never change project "
    "files, and print the program's actual output (and `echo \"exit=$?\"` when the exit code matters).\n"
    "- Do NOT print or assert expected values; only show what the program does. Each command must finish in a few "
    "seconds and must not need a network, a browser or a GUI.\n"
    "- rule: the rule in a few words, as the text states it.\n\n<task>\n{task}\n</task>\n\n<text>\n{text}\n</text>")


def make_probes(seed_dir, task, max_total=10):
    """EV_PROBES: [{rule, command}] from the task and each doc, written once per task by the 26B"""
    import agent_g as G
    files = sorted(p for p in G.files_of(seed_dir) if not p.startswith((".agent/",)))[:60]
    docs = [(rel, G.read(seed_dir, rel, 8000)) for rel in files
            if rel.lower().endswith((".md", ".txt", ".rst")) and rel.lower() != "license" and not rel.startswith(("data/", "tests/"))]
    srcs = [("task", task[:4000])] + [(rel, txt) for rel, txt in docs][:4]
    schema = {"type": "object", "properties": {"probes": {"type": "array", "maxItems": 4, "items": {
        "type": "object", "properties": {"rule": {"type": "string", "maxLength": 200}, "command": {"type": "string", "maxLength": 700}},
        "required": ["rule", "command"]}}}, "required": ["probes"]}

    def one(src):
        name, text = src
        return G.structured_safe(lambda: G.structured(PROBE_PROMPT.format(n=4, files=", ".join(files), task=task[:3000],
                                                                          text=text), schema, system=G.SYS)) or {}
    with ThreadPoolExecutor(4) as ex:
        res = list(ex.map(one, srcs))
    out, seen = [], set()
    for d in res:
        for p in d.get("probes", []):
            c = str(p.get("command", "")).strip().replace("'exit=$?'", '"exit=$?"')   # single quotes kept $? literal
            # a probe must look at the engineer's files, not replace them: cycle 40 CAD probes wrote their own model
            # (printf ... > model.py) and measured that; any redirect or tee into a project path drops the probe
            writes_project = re.search(r"(>>?|\btee\b(\s+-a)?)\s*(?!/tmp/|/dev/|&)['\"]?[\w.]", c)
            # probes that make up their own input files were the ones that went wrong (cycle 40 paginate: "id:1,author:A"
            # lines for a JSONL reader, printf "%n"): a correct program fails on them and Jev may call that a violation.
            # Kept: probes on the provided data or with command-line arguments only.
            makes_input = re.search(r"\b(printf|echo|cat)\b[^|;&]*>>?\s*/tmp/|<<", c)
            if c and c not in seen and not writes_project and not makes_input and not re.search(r"\b(rm|mv|cp|sed -i)\b", c):
                seen.add(c); out.append({"rule": str(p.get("rule", ""))[:200], "command": c})
    return out[:max_total]


def collect(ws, seed_dir, task, limit=9000, probes=None, budget=None):
    """-> one text block of facts about the result in ws (seed_dir: the files as given, for what changed)"""
    seed = files(seed_dir) if seed_dir and os.path.isdir(seed_dir) else {}
    now = files(ws)
    changed = sorted(p for p in now if seed.get(p) != now[p])
    removed = sorted(p for p in seed if p not in now)
    parts = ["Files created or changed: " + (", ".join(changed[:40]) or "none")
             + ("\nFiles removed: " + ", ".join(removed) if removed else "")]
    box = base.Sandbox(ws)
    try:
        # a provided server must run while the task's commands run (browser tasks: without it every command fails
        # to connect, which says nothing about the result)
        try:
            start, env = setup(ws, task)
        except Exception:
            start, env = "", {}
        if not start:
            servers = [p for p in seed if re.search(r"(^|/)(server|app)\.py$", p) and not p.startswith("tests/")][:1]
            start = "".join(f"(python3 {p} >/tmp/server.log 2>&1 &) ; sleep 2; " for p in servers)
        start = "".join(f"export {k}={shlex.quote(v)}; " for k, v in env.items()) + start
        if start:
            parts.append("Set up before running the task's commands (from the docs): " + start)
        # EV_GENERATORS=1 (v7w on): a missing sample input is made by a provided generator first. Off by default so a
        # running v7q measurement keeps the evidence it started with.
        gens = generators(seed_dir, seed) if seed_dir and os.environ.get("EV_GENERATORS") == "1" else None
        cmds = [c for c in task_commands(task, seed, gens) if "unittest" not in c and c not in start
                and not re.search(r"(^|/)(server|app)\.py( |$)", c)]
        box.sh(FRESH + "true", timeout=60)
        budget, t0 = float(budget or os.environ.get("EV_BUDGET", "180")), time.time()
        for c in cmds:   # in order, in one fresh copy (/tmp/w), so later commands see what earlier ones made
            left = budget - (time.time() - t0)
            if left < 10:   # cycle 33 sec_firewall: the gate ran 9+ minutes with no limit on the whole
                parts.append(f"$ {c}\n(not run: the harness's {int(budget)} s time budget for collecting facts was used up)")
                continue
            code, out, err = box.sh("cd /tmp/w && export PYTHONPATH=/tmp/w && " + start + c, timeout=min(120, int(left)))
            parts.append(f"$ {c}\nexit code: {code}\n" + base.clip((out + ("\n[stderr]\n" + err if err.strip() else "")).strip(), 1500))
        if os.environ.get("EV_DOCEX") == "1" and seed_dir:
            parts += run_doc_examples(box, seed_dir, task, start)
        fresh = os.path.join(ws, ".agent", "fresh")
        if cmds:   # the outputs as the task's commands make them now, not files left over from earlier runs
            box.sh("rm -rf /work/.agent/fresh; mkdir -p /work/.agent && cp -a /tmp/w /work/.agent/fresh", timeout=60)
        if probes:
            # EV_PROBES: commands written from the docs (make_probes) that exercise single rules with small inputs;
            # only their real output becomes a fact, nobody's expectation (26B-written expected values were wrong
            # too often, 10-23 v7z). Run after the copy above so they do not change the listed output files.
            box.sh(FRESH + "true", timeout=60)
            for p in probes:
                left = budget - (time.time() - t0)
                if left < 15:
                    parts.append("(remaining probes not run: time budget used up)")
                    break
                code, out, err = box.sh("cd /tmp/w && export PYTHONPATH=/tmp/w && " + start + p["command"],
                                        timeout=min(20, int(left)))
                # a probe that is itself broken says nothing about the result and could read as a violation (cycle 40
                # html_fix: jsdom pseudo-code): command not found, a shell syntax error, or the probe's own inline
                # Python failing to parse / naming something that does not exist / importing a missing module
                if code in (2, 126, 127) or re.search(r'File "<string>", line \d+[^\n]*\n(?:(?!\s*File ")[^\n]*\n)*?(SyntaxError|NameError|IndentationError|ModuleNotFoundError)', err + out):
                    continue
                parts.append(f"Probe of the rule \"{p['rule']}\" (command written by the harness from the docs, not by "
                             f"the engineer):\n$ {p['command']}\nexit code: {code}\n"
                             + base.clip((out + ("\n[stderr]\n" + err if err.strip() else "")).strip(), 600))
        if os.path.isdir(os.path.join(ws, "tests")):
            code, out, err = box.sh(FRESH + "python3 -m unittest discover -s tests 2>&1 | tail -6",
                                    timeout=max(30, min(180, int(budget - (time.time() - t0)))) if cmds else 180)
            parts.append(f"$ python3 -m unittest discover -s tests\n{(out + err).strip()[-600:]}")
        src = fresh if os.path.isdir(fresh) else ws
        now2 = files(src)
        made = sorted(p for p in now2 if seed.get(p) != now2[p])
        outs = [p for p in made if p.endswith(TEXT_OUT) and not p.startswith(("tests/", "docs/")) and os.path.getsize(os.path.join(src, p)) < 2e6]
        for p in outs[:5]:
            if p.endswith(".html"):
                continue
            parts.append(f"Output file {p}" + (" (after running the commands above)" if src == fresh else "") + ": " + byte_facts(os.path.join(src, p)))
            exp = [e for e in now2 if "expected" in os.path.basename(e).lower() and os.path.splitext(e)[1] == os.path.splitext(p)[1]]
            for e in exp[:1]:
                same = open(os.path.join(src, e), "rb").read() == open(os.path.join(src, p), "rb").read()
                parts.append(f"{p} compared byte by byte with the provided {e}: {'identical' if same else 'DIFFERENT'}")
                if not same and os.environ.get("EV_DIFFLINE") == "1":
                    parts.append(first_diff(os.path.join(src, e), os.path.join(src, p), e, p))
        dbs = [p for p in made if p.lower().endswith((".db", ".sqlite", ".sqlite3"))][:2]
        for p in dbs:
            rel = os.path.relpath(os.path.join(src, p), ws)
            code, out, err = box.sh("cd /work && python3 - <<'PY'\nimport sqlite3\nc = sqlite3.connect(" + repr(rel) + ")\n"
                                    "for n, sql in c.execute(\"select name, sql from sqlite_master where sql is not null\"):\n"
                                    "    print(sql)\n"
                                    "    if sql.upper().startswith('CREATE TABLE'): print('  rows:', c.execute(f'select count(*) from \"{n}\"').fetchone()[0], '| first:', c.execute(f'select * from \"{n}\" limit 3').fetchall())\n"
                                    "print('user_version', c.execute('pragma user_version').fetchone()[0], 'foreign_keys', c.execute('pragma foreign_keys').fetchone()[0])\nPY", timeout=60)
            parts.append(f"SQLite database {p}" + (" (after running the commands above)" if src == fresh else "") + ":\n" + base.clip((out + err).strip(), 1500))
        image = base.sandbox_for(ws)[0] or ""
        html = [p for p in changed if p.endswith(".html")][:3]
        if not html and os.environ.get("EV_DIFFLINE") == "1" and any(p.endswith((".js", ".mjs", ".css")) for p in changed):
            # only app.js/style.css changed: the page that loads them is what runs (10-23 html_fix: a null
            # addEventListener error in app.js went unseen because index.html itself was unchanged)
            html = sorted((p for p in now if p.endswith(".html") and not p.startswith(("tests/", "docs/", ".agent/"))),
                          key=lambda p: (p.count("/"), p != "index.html"))[:3]
        if html and "web" in image:
            open(os.path.join(ws, ".agent_probe.py"), "w").write(WEB_PROBE)
            code, out, err = box.sh("cd /work && python3 .agent_probe.py " + " ".join(html), timeout=120)
            line = next((l for l in out.splitlines() if l.startswith("@@")), None)
            if line:
                for f, d in json.loads(line[2:]).items():
                    parts.append(f"Chromium opened {f}: console errors {d['console_errors'] or 'none'}\n"
                                 f"elements with id: {' '.join(d['ids'])}\nvisible text: {d['text']!r}")
            else:
                parts.append("Chromium probe failed: " + (out + err)[-300:])
            os.remove(os.path.join(ws, ".agent_probe.py"))
    finally:
        box.close()
        shutil.rmtree(os.path.join(ws, ".agent", "fresh"), ignore_errors=True)
    return base.clip("\n\n".join(parts), limit + (7000 if probes else 0))


# ---------------------------------------------------------------- judging requirements against the facts
# One function for the gate (agent_v5 v7q) and for the replay scoring (jev_replay.py), so both stay the same.
# The shared part (task + facts) comes first and the requirement last, so the server can reuse the cached prefix.
HEAD = ("Task given to an engineer:\n<task>\n{task}\n</task>\n\nFacts about the engineer's finished result, collected "
        "automatically by running it (not written by the engineer):\n<facts>\n{facts}\n</facts>\n\n")
ASK = {
    "violated": "One requirement of the task:\n{req}\n\nDo these facts clearly show that the result violates this requirement? "
                "Answer violated=false if the facts show it is met, or if they say nothing about this requirement.",
    "consistent": "One requirement of the task:\n{req}\n\nAre these facts consistent with the requirement being met? Answer "
                  "consistent=false only if a fact shown above directly contradicts the requirement.",
    "decidable": "One requirement of the task:\n{req}\n\nCan a reader decide whether this requirement is met just by reading these "
                 "facts, with no calculation of their own, no guessing about inputs not shown, and no knowledge of the code? "
                 "Answer decidable=true only if so.",
    "direct": "One requirement of the task:\n{req}\n\nIs there a fact above that by itself shows, without any calculation, sorting, "
              "counting or reasoning about code, whether this requirement is met (for example a stated line-end count, an exact "
              "output line, an error message, or a 'DIFFERENT'/'identical' comparison)? Answer direct=true only if so.",
}


ASK_REQ_FIRST = {
    "decidable": ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n"
                  "<facts>\n{facts}\n</facts>\n\nCan a reader decide whether this requirement is met just by reading these facts, "
                  "with no calculation of their own, no guessing about inputs not shown, and no knowledge of the code? "
                  "Answer decidable=true only if so."),
    "direct": ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n<facts>\n{facts}\n</facts>\n\n"
               "Is there a fact above that by itself shows, without any calculation, sorting, counting or reasoning about code, "
               "whether this requirement is met (for example a stated line-end count, an exact output line, an error message, "
               "or a 'DIFFERENT'/'identical' comparison)? Answer direct=true only if so."),
    "shown": ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n<facts>\n{facts}\n</facts>\n\n"
              "Quote the single fact line above that shows this requirement is NOT met, or answer shown=false if no line shows it. "
              "Does such a line exist? Answer shown=true only if a specific line above contradicts the requirement."),
}


GROUNDED = ("Task:\n<task>\n{task}\n</task>\n\nProject documents:\n<docs>\n{docs}\n</docs>\n\nProposed requirement:\n{req}\n\n"
            "Is this a requirement of THIS task, stated in the task or the documents above (in other words, or as a direct "
            "consequence of what they say)? Answer grounded=false if it is not there, adds a detail they do not give, or comes "
            "from an example, sample code or general advice in a tool manual rather than from what this task asks for.")


def docs_text(root):
    out = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP and d not in ("data", "out", "tests")]
        for fn in sorted(fns):
            if fn.lower().endswith((".md", ".txt", ".rst")) and fn.lower() != "license":
                rel = os.path.relpath(os.path.join(dp, fn), root)
                out.append(f"=== {rel} ===\n" + open(os.path.join(dp, fn), errors="replace").read()[:6000])
    return "\n\n".join(out)[:12000]


def judge_reqs(task, reqs, facts, docs="", workers=None):
    """-> (flagged requirements, scores). Flagged = judged violated (p>=0.9), inconsistent with being met (p<0.5), a
    line of the facts is shown to contradict it, and the requirement is really in the task/docs (the model invents
    some, e.g. "'1.4.0+build-7' is an invalid version" for semver). Later questions run only on what the earlier ones
    flag. Replay on 120 finished q25 results (10-23): 0 of 57 passing flagged, 25 of 63 failing caught, CRLF 5 of 5.
    (decidable/direct questions were dropped: their answers changed from run to run on the same kind of facts.)"""
    import concurrent.futures as cf
    import agent_g as G
    # the servers take 6 requests at once in total (3 x -np 2); more only queues and evicts the cached prefix
    workers = workers or int(os.environ.get("JEV_WORKERS", "2"))
    head = HEAD.format(task=task[:5000], facts=facts)
    reqs = [r for r in reqs if len(r) <= 250]   # long compound items were judged unreliably
    ask = lambda k, r: G.judge(head + ASK[k].format(req=r), k)
    vt = float(os.environ.get("GATE_VIOLATED", "0.9"))
    # GATE_REPLAY=1: record all four probabilities for every violated>=0.7 candidate so a threshold sweep can run
    # offline (the 4-stage funnel below only ever computed them for violated>=0.9)
    rec = os.environ.get("GATE_REPLAY") == "1"
    c1t = 0.7 if rec else vt
    with cf.ThreadPoolExecutor(workers) as ex:
        ps = list(ex.map(lambda r: ask("violated", r), reqs))
        c1 = [i for i, p in enumerate(ps) if p >= c1t]
        ms = dict(zip(c1, ex.map(lambda i: ask("consistent", reqs[i]), c1)))
        c2 = [i for i in c1 if ms[i] < 0.5 or rec]
        sh = dict(zip(c2, ex.map(lambda i: G.judge(ASK_REQ_FIRST["shown"].format(req=reqs[i], facts=facts), "shown"), c2)))
        c3 = [i for i in c2 if sh[i] >= 0.5 or rec]
        gr = dict(zip(c3, ex.map(lambda i: G.judge(GROUNDED.format(task=task, docs=docs, req=reqs[i]), "grounded"), c3)))
    bad = [reqs[i] for i in c3 if gr.get(i, 0) >= 0.5 and ps[i] >= vt and ms.get(i, 1) < 0.5 and sh.get(i, 0) >= 0.5]
    scores = {"n": len(reqs), "violated": [round(p, 3) for p in ps],
              "cand": [(reqs[i][:80], round(ps[i], 3), round(ms.get(i, -1), 3), round(sh.get(i, -1), 3), round(gr.get(i, -1), 3)) for i in c1]}
    return bad, scores
