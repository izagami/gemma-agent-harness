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
import hashlib, json, os, re, shlex, shutil, sys, time
from concurrent.futures import ThreadPoolExecutor
import agent as base
import judge

KEEP_FULL = 5
CAD_IMAGE = os.environ.get("CAD_IMAGE", "localhost/local-agent-cad")  # built from cad/Dockerfile.cad
CTX_SOFT_LIMIT = 90000  # characters incl. call arguments; above this, old outputs and arguments are masked in one batch
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

SYSTEM_CAD_RULES = """
CAD tasks (CadQuery 2.8, units mm):
C1. Write the part in model.py and assign it to `result`. Build and measure it with
    `python3 /opt/cad/cadtool.py model.py`: it writes model.step/.stl/.png and prints the bounding box, volume,
    validity and every hole/boss/fillet with diameter, axis, length and position. Run it after every change.
C2. Before calling finish, compare EVERY number in the task with the cadtool report (sizes, positions, hole
    diameters and counts, depths) and look at model.png with view_image. Fix any difference first.
C3. The spec test (.agent/spec_test.py) checks the model itself:
      import sys; sys.path.insert(0, "/opt/cad"); from cadtool import load, size, features
      s = load("model.py"); assert size(s) == (100.0, 60.0, 8.0)
      holes = [f for f in features(s) if f["kind"] == "hole"]; assert len(holes) == 4 and holes[0]["diameter"] == 6.6
    features() kinds: "hole", "boss", "inner fillet", "outer fillet"; "at" = where the axis crosses the plane through 0.
C4. Facts (checked): Workplane("XY").extrude(h) goes +Z; Workplane("XZ").extrude(h) goes -Y (use a negative h for +Y);
    Workplane("YZ").extrude(h) goes +X. box(x, y, z) is centred on the origin; box(x, y, z, centered=(True, True, False))
    puts the bottom on Z=0. faces(">Z").workplane() keeps the global X/Y coordinates for points. workplane(offset=z)
    starts at height z. polygon(n, d): d is the circumscribed diameter, one vertex on +X. slot2D(length, width):
    length is end to end. polarArray(r, 0, 360, n) starts on +X. Revolve: Workplane("XZ").polyline(pts).close()
    .revolve(360, (0, 0, 0), (0, 1, 0)) turns about the global Z axis (pts are (radius, z)).
C5. Holes: .pushPoints([(x, y), ...]).hole(d) cuts through everything below the workplane; cboreHole(d, cbore_d,
    cbore_depth); cskHole(d, csk_d, 90); cutBlind(-depth) for pockets; cutThruAll() for through cuts.
    Edges: .edges("|Z").fillet(r) rounds the vertical edges; .faces(">Z").edges().chamfer(c). Combine solids with
    a.union(b) / a.cut(b); make each extra solid with its own Workplane and translate((x, y, z)) if needed.
    Open box: .faces(">Z").shell(-t) (negative = walls inward). Solids that only touch along a line are not one
    solid: make them overlap.
C6. Complex parts: list the features first (todo), then build each one as its own named solid in model.py
    (base = ..., boss = ..., holes = ...), check its size and position with cadtool before combining, and combine
    step by step (body = base.union(boss); body = body.cut(holes)). Cut holes and bores last, after every union,
    so no later solid fills them again.
C7. More facts (checked): solid.rotate((0, 0, 0), (0, 0, 1), deg) turns about Z, +X towards +Y; .mirror("YZ") mirrors
    across X=0 (mirror("YZ", union=True) keeps both); rarray(dx, dy, nx, ny) is a centred grid of points;
    .transformed(rotate=(a, 0, 0)) tilts the workplane about X; extrude(d, both=True) goes d both ways.
    Sweep: path = Workplane("XZ").lineTo(0, 40).radiusArc((40, 80), 40).lineTo(100, 80) (points are (X, Z));
    Workplane("XY").circle(r).sweep(path, transition="round") makes a pipe whose start is at the origin going +Z.
    Loft: Workplane("XY").rect(40, 40).workplane(offset=30).circle(10).loft(). A profile in a side plane:
    Workplane("YZ").workplane(offset=x0).polyline([(y, z), ...]).close().extrude(width) (points are (Y, Z)).
C8. Never guess an API. Before using a method you are not sure of, and after any AttributeError or TypeError from
    CadQuery, look it up: `python3 /opt/cad/cadtool.py --api fillet` prints the real signatures and docs of every
    method whose name contains the word. Edge/face positions: e.Center() (a method), not e.center.
C10. Objects with many parts (vehicles, furniture, machines, buildings) or anything that is easier to place by
    coordinates: use the building blocks in /opt/cad/cadparts.py (from cadparts import *): box(x0, x1, y0, y1, z0, z1),
    cyl_x/cyl_y/cyl_z (axis position, radius, start, end), cone_x/cone_y/cone_z (tapered: radius at start and end),
    loft_x([(x, y, z, r), ...]) (round body through circular stations: fuselage, bottle), tube_y, sphere, profile_xz/profile_xy/profile_yz (outline
    points + extrusion range), loft_z (two rectangles given as (x_min, x_max, y_min, y_max)), round_edges, wheel_y,
    mirror_y (left/right pair), union_all. Every size is a min/max coordinate, so no workplane rules are needed.
    Read the closest example first (ls /opt/cad/examples; e.g. car.py) and adapt its pattern. For colours, list the
    parts instead of `result`: PARTS = [("body", body, (0.8, 0.1, 0.1)), ("glass", glass, (0.1, 0.1, 0.2)), ...];
    cadtool then reports every part's box and writes a coloured model.glb.
C9. Rounded inner corners of a pocket or cavity: make the cavity as its own solid (rect(...).extrude(h).edges("|Z")
    .fillet(r)) and cut it from the body, instead of selecting inner edges after cutting.
"""

VIEW_IMAGE_TOOL = {"type": "function", "function": {"name": "view_image", "description": "Look at an image file (PNG/JPEG) in /work, for example model.png from cadtool.",
                   "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}


THINK_TOOL = {"type": "function", "function": {"name": "think", "description": "Write down your reasoning or plan. It does not change anything. Use it instead of putting reasoning in commands, comments or files.",
    "parameters": {"type": "object", "properties": {"thought": {"type": "string"}}, "required": ["thought"]}}}

THINK_ABORT = int(os.environ.get("THINK_ABORT", "1000"))
THINK_CUT = " [... cut off by the harness at the length limit]"
CONTENT_ABORT = int(os.environ.get("CONTENT_ABORT", "1500"))
EDIT3 = os.environ.get("EDIT3") == "1"   # kept content on a missing path, comment-reasoning stop
VISION = os.environ.get("VISION") == "1"   # the model server accepts images (vllm_lane.sh VISION=1)
TEXT_CUT = " [... cut off by the harness: plain text is not run or saved]"


def jev_decided(text):
    """v7m: Jev decides whether a think in progress already names its next action (then the rest is padding)."""
    import agent_g as G
    q = ("Below is the beginning of a coding agent's private reasoning, still being written.\n\n<<<\n" + text[-3000:] +
         "\n>>>\n\nHas it already decided one concrete next action (a specific command to run, file to read or edit, "
         "or check to make)? Answer true only if that action is stated clearly enough to do right now.")
    return G.judge(q, key="decided") > 0.5


TYPED_THINK = {"type": "object", "additionalProperties": False, "required": ["known", "next"], "properties": {
    "known": {"type": "string", "maxLength": 400}, "next": {"type": "string", "maxLength": 200}}}


# THINK_SCHEMA=2: the v7o {known} field restated ~400 characters of earlier work every time, with unchecked claims
# ("correctly handles ...") and few new facts (10-24 cycle 14 db_migrate); now one narrow judgment plus one new fact
TYPED_THINK2 = {"type": "object", "additionalProperties": False, "required": ["last_result", "learned", "next"], "properties": {
    "last_result": {"type": "string", "enum": ["as expected", "unexpected", "error", "nothing new"]},
    "learned": {"type": "string", "maxLength": 200}, "next": {"type": "string", "maxLength": 160}}}


# THINK_SCHEMA=3: schema 2, and when the two latest thinks both said error/unexpected (cycle 16 browser_export: 12 of
# 15 thinks were "error", one approach retried), the think shows the tried actions and asks for the shared assumption
# and a different action
TYPED_STUCK = {"type": "object", "additionalProperties": False, "required": ["failing", "assumption", "next"], "properties": {
    "failing": {"type": "string", "maxLength": 200}, "assumption": {"type": "string", "maxLength": 200},
    "next": {"type": "string", "maxLength": 160}}}


def earlier_thoughts(messages):
    out = []
    for m in messages:
        for c in m.get("tool_calls") or []:
            if c["function"]["name"] == "think":
                try:
                    out.append(str(json.loads(c["function"]["arguments"]).get("thought", "")))
                except ValueError:
                    pass
    return out


THINK_STUCK = "\n[harness: three results in a row went wrong]"


def judge_last(body):
    """v7v: one Jev-style typed judgment per think, ~10 tokens: how did the latest tool output compare with what was
    expected. The free think stays (cut at THINK_ABORT); only the narrow judgment is typed."""
    import urllib.request
    b = {k: v for k, v in body.items() if k not in ("stream", "stream_options")}
    b["messages"] = b["messages"] + [{"role": "user", "content": "[harness] One word: how did the latest tool output "
                                      "compare with what you expected?"}]
    b.update(max_tokens=12, temperature=0, tool_choice="none", response_format={"type": "json_schema", "json_schema": {
        "name": "j", "strict": True, "schema": {"type": "object", "additionalProperties": False, "required": ["r"],
        "properties": {"r": {"type": "string", "enum": ["as expected", "unexpected", "error", "nothing new"]}}}}})
    req = urllib.request.Request(base.API, json.dumps(b).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + base.API_KEY})
    with urllib.request.urlopen(req, timeout=120) as r:
        txt = json.load(r)["choices"][0]["message"]["content"]
    m = re.search(r'"r"\s*:\s*"([a-z ]+)"', txt)
    return m.group(1) if m else "nothing new"


def trace_facts(messages, workdir):
    """THINK_SCHEMA=4: facts for the typed think, collected by the harness: when the latest tool output has a
    traceback, the lines each frame points at, read from the workspace as they are now. Cycle 20 db_repo spent ~30
    steps on one "Incorrect number of bindings" error; its stuck thinks said "the code looks correct" and never looked
    at the lines the traceback named."""
    if not workdir:
        return ""
    last = next((m for m in reversed(messages[-6:]) if m.get("role") == "tool"), None)
    txt = str((last or {}).get("content") or "")
    frames = re.findall(r'File "([^"]+)", line (\d+)', txt)
    out, seen = [], set()
    for path, n in reversed(frames):
        rel = path[len("/work/"):] if path.startswith("/work/") else path
        if rel.startswith("/") or "site-packages" in rel or (rel, n) in seen:
            continue
        seen.add((rel, n))
        try:
            lines = open(os.path.join(workdir, rel), errors="replace").read().splitlines()
        except OSError:
            continue
        k = int(n)
        out.append(f"{rel}:{k}\n" + "\n".join(f"{i:4d}{'>' if i == k else ' '} {lines[i - 1]}"
                                             for i in range(max(1, k - 2), min(len(lines), k + 2) + 1)))
        if len(out) == 4:
            break
    if not out:
        return ""
    exc = [l for l in txt.splitlines() if re.match(r"\w+(Error|Exception)\b", l.strip())][-1:]
    return ("Facts collected by the harness from the latest traceback (the files as they are now, innermost frame "
            "first):\n" + "\n\n".join(out) + ("\nRaised: " + exc[0].strip() if exc else ""))[:1800]


def think_tokens(schema):
    """room for every field at its cap (~2.5 characters per token, more for Japanese) plus JSON; 400 was set for
    200 + 160 characters"""
    return max(400, 150 + sum(v.get("maxLength", 20) for v in schema["properties"].values()) // 2)  # base: 400 as before


def with_caps(schema):
    """THINK_LEARNED / THINK_NEXT: caps of the typed think's conclusion fields (defaults 200 / 160). 10-24, 797 typed
    thinks: learned hit its 200-character cap in 43% (cut mid-sentence by the grammar), next its 160 in 11%"""
    caps = {"learned": os.environ.get("THINK_LEARNED"), "next": os.environ.get("THINK_NEXT")}
    if not any(caps.values()):
        return schema
    props = {k: (dict(v, maxLength=int(caps[k])) if caps.get(k) else v) for k, v in schema["properties"].items()}
    return dict(schema, properties=props)


def with_free(schema, n, after=None):
    """THINK_FREE=N: the typed think gets a free-text "reasoning" field of at most N characters (placed after the field
    `after`, before the conclusions), so a plan fits (schema 3's 200-character fields could not hold one, 10-24) while
    the length stays capped by the grammar"""
    if not n:
        return schema
    props = {}
    if after is None:
        props["reasoning"] = {"type": "string", "maxLength": n}
    for k, v in schema["properties"].items():
        props[k] = v
        if k == after:
            props["reasoning"] = {"type": "string", "maxLength": n}
    return dict(schema, properties=props, required=list(props))


# THINK_SCHEMA=6: the "last_result" judgment is taken away from the model. The think states what its action should
# show ("expect"); at the next think the harness puts that expectation next to the action's real output and asks
# Jev whether they match (23/24 on hand-labelled pairs, 10-24), and adds the exit code / traceback as facts.
# Stuck = two expectations in a row not met. (Schema 3's own 4-way answer: "as expected" 6 of 1436 times, "error"
# for 203 outputs with no error in them.)
TYPED_THINK6 = {"type": "object", "additionalProperties": False, "required": ["learned", "next", "expect"], "properties": {
    "learned": {"type": "string", "maxLength": 200}, "next": {"type": "string", "maxLength": 160},
    "expect": {"type": "string", "maxLength": 300}}}


def EDIT_EXPECT():
    return ("for a file edit: what your last check will show when the harness re-runs it after the edit"
            if os.environ.get("THINK_AUTOCHECK") == "1" else '"none" for a file edit')


def prev_action(messages):
    """the latest non-think tool call (name, parsed-args) before now"""
    for m in reversed(messages):
        for c in reversed(m.get("tool_calls") or []):
            if c["function"]["name"] != "think":
                try:
                    a = json.loads(c["function"]["arguments"] or "{}")
                except ValueError:
                    a = {}
                return c["function"]["name"], (a if isinstance(a, dict) else {})
    return None, {}


def verdict_restrict(st, messages, tools, offered, log):
    """THINK_SCHEMA=7 (verdict_act): the Jev verdict on the last expectation restricts the NEXT step's tools, so the
    verdict changes behaviour instead of only being written down (10-24: schema 6's verdict left the action mix
    unchanged). Every lock keeps investigation (bash, read_file) available and lifts within a few steps, so a wrong
    verdict costs at most a check step or two."""
    _, met = last_outcome(messages)
    name, args = prev_action(messages)
    only = lambda keep: [t for t in offered if t["function"]["name"] in keep]
    st.unmet = getattr(st, "unmet", 0)
    st.metrun = getattr(st, "metrun", 0)
    st.invest = getattr(st, "invest", 0)
    if met is False:
        st.unmet += 1; st.metrun = 0
        if name in ("write_file", "edit_file") and args.get("path"):
            st.suspect = base.safe_path(str(args["path"]))   # do not re-edit the file just changed until it is checked
    elif met is True:
        st.metrun += 1; st.unmet = 0; st.suspect = None
    if name == "bash" or name == "read_file":
        st.suspect = None   # the suspect file (or the state) was just investigated
    # stuck: two unmet in a row -> investigate only, for up to 3 steps
    if st.unmet >= 2 and st.invest < 3:
        st.invest += 1
        log({"verdict_lock": "investigate", "unmet": st.unmet, "step_invest": st.invest})
        return only({"bash", "read_file", "think"})
    if st.unmet < 2:
        st.invest = 0
    # one unmet: block re-editing the suspect file (it must be checked or read first)
    if met is False and getattr(st, "suspect", None):
        blocked = [t for t in offered if not (t["function"]["name"] in ("write_file", "edit_file"))]
        log({"verdict_lock": "no-reedit", "file": st.suspect})
        return blocked
    # two met in a row: nudge to finish (keep finish offered, it already is)
    if st.metrun >= 2:
        log({"verdict_lock": "nudge-finish", "metrun": st.metrun})
    return offered


def last_outcome(messages):
    """the latest typed think's expectation and the output of the action fused with it -> (text, met or None)"""
    exp, out, tc_id = None, None, None
    for i in range(len(messages) - 1, -1, -1):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            calls = m["tool_calls"]
            if calls[0]["function"]["name"] == "think":
                try:
                    th = json.loads(calls[0]["function"]["arguments"]).get("thought", "")
                except ValueError:
                    th = ""
                # only a command's output can meet an expectation; after write_file / edit_file the output is "wrote ..."
                # (the first try compared "the tests pass" with an edit's output)
                if "\nExpect: " in th and len(calls) > 1 and (calls[1]["function"]["name"] == "bash" or (
                        os.environ.get("THINK_AUTOCHECK") == "1" and calls[1]["function"]["name"] in ("write_file", "edit_file"))):
                    exp = th.split("\nExpect: ", 1)[1].split("\n", 1)[0]
                    tc_id = calls[1].get("id")
                break
    if not exp:
        return "", None
    out = next((str(m.get("content", "")) for m in messages if m.get("role") == "tool" and m.get("tool_call_id") == tc_id), None)
    if out is None:
        return "", None
    import agent_g as G
    p = G.judge(f"Before running a command, an agent wrote what it expected:\n<expected>\n{exp}\n</expected>\n\nThe command's "
                f"actual output:\n<output>\n{out[-3000:]}\n</output>\n\nDoes the actual output match what was expected "
                "(every stated detail)?", key="matches")
    code = re.search(r"exit code: (-?\d+)", out)
    facts = [f"exit code {code.group(1)}" if code else None, "a traceback" if "Traceback (most recent call last)" in out else None]
    facts = ", ".join(f for f in facts if f)
    met = p >= 0.5
    return (f"[harness] Your last action was expected to show: {exp}\nJev compared it with the real output: "
            f"{'MET' if met else 'NOT MET'} (p={p:.2f})" + (f"; the output has {facts}" if facts else "") + "."), met


def typed_think6(b, workdir=None):
    import urllib.request
    note, met = last_outcome(b["messages"])
    prev = [t for t in earlier_thoughts(b["messages"]) if t.startswith("Last result: ")][-1:]
    stuck = met is False and bool(prev) and prev[-1].startswith("Last result: expectation not met")
    if stuck:
        tried = "\n".join("- " + t.split("Next: ", 1)[-1].split("\n", 1)[0] for t in earlier_thoughts(b["messages"])[-3:] if "Next: " in t)
        ask = (note + "\n\n[harness] Two expectations in a row were not met. Actions tried:\n" + tried + "\nThink in JSON: "
               "failing = what keeps failing (the exact symptom); assumption = the belief those tries share that may be wrong; "
               "next = one concrete action that tests that belief or takes a different route; expect = what the output of "
               "that very action will show if it works (concrete: counts, exit code, key lines; " + EDIT_EXPECT() + ").")
        schema = {"type": "object", "additionalProperties": False, "required": ["failing", "assumption", "next", "expect"],
                  "properties": dict(TYPED_STUCK["properties"], expect={"type": "string", "maxLength": 300})}
    else:
        ask = ((note + "\n\n" if note else "") + "[harness] Think in JSON, briefly: learned = the one new fact the latest output "
               "showed (not a summary of earlier work); next = the one concrete action to take now; expect = what the output of that "
               "very action will show if your understanding is right (concrete: counts, exit code, key lines; " + EDIT_EXPECT() + ").")
        schema = TYPED_THINK6
    schema = with_caps(schema)
    b["messages"] = b["messages"] + [{"role": "user", "content": ask}]
    b.update(max_tokens=think_tokens(schema), tool_choice="none", response_format={"type": "json_schema", "json_schema": {
        "name": "think", "strict": True, "schema": schema}})
    req = urllib.request.Request(base.API, json.dumps(b).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + base.API_KEY})
    with urllib.request.urlopen(req, timeout=300) as r:
        txt = json.load(r)["choices"][0]["message"]["content"]
    f = {k: re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)' % k, txt) for k in schema["properties"]}
    # strict=False: a raw newline/tab inside a field broke the whole think (cycle 42 vba_sales "Invalid control character")
    f = {k: json.loads('"' + v.group(1) + '"', strict=False) if v else "" for k, v in f.items()}
    head = ("Last result: stuck" if stuck else "Last result: " + ("expectation met" if met else "expectation not met"
            if met is False else "no expectation"))
    body_ = (f"Failing: {f['failing']} Doubtful assumption: {f['assumption']}" if stuck else f"Learned: {f['learned']}")
    return f"{head}. {body_}\nNext: {f['next']}\nExpect: {f['expect']}"


def typed_think(body, workdir=None):
    """v7n: the think tool made a Jev-style typed answer. The free-text think is dropped as soon as its name streams
    in, and the same conversation (prefix cached) is asked for {known, next} under a length-limited JSON schema:
    ~1.5 s and ~120 tokens on vLLM (10-24) instead of 31 s for a free think."""
    import urllib.request
    b = {k: v for k, v in body.items() if k not in ("stream", "stream_options")}
    if os.environ.get("THINK_SCHEMA") == "6":
        return typed_think6(b, workdir)
    v2 = os.environ.get("THINK_SCHEMA") in ("2", "3", "4")
    facts = trace_facts(b["messages"], workdir) if os.environ.get("THINK_SCHEMA") == "4" else ""
    prev = earlier_thoughts(b["messages"])[-3:]
    stuck = (os.environ.get("THINK_SCHEMA") in ("3", "4") and len(prev) >= 2 and
             all(t.startswith(("Last result: error", "Last result: unexpected")) for t in prev[-2:]))
    # a stuck think is followed by an ordinary one, which judges whether the different action worked (cycle 17: with
    # stuck thinks counted as failures, sec_firewall stayed stuck for 21 of 25 thinks)
    free = int(os.environ.get("THINK_FREE", "0"))
    if stuck:
        tried = "\n".join("- " + t.split("Next: ", 1)[-1] for t in prev if "Next: " in t)
        b["messages"] = b["messages"] + [{"role": "user", "content": (
            (facts + "\n\n" if facts else "") +
            "[harness] The latest results were errors or unexpected again. Actions tried:\n" + tried + "\nThink in JSON: "
            "failing = what keeps failing (the exact symptom); assumption = the belief those tries share that may be wrong; "
            "next = one concrete action that tests that belief or takes a different route, not one of the tries above.")}]
        b.update(max_tokens=think_tokens(with_free(with_caps(TYPED_STUCK), free, "failing")), tool_choice="none", response_format={"type": "json_schema", "json_schema": {
            "name": "think", "strict": True, "schema": with_free(with_caps(TYPED_STUCK), free, "failing")}})
    ask = ("[harness] Think in JSON, briefly: last_result = how the latest tool output compares with what you expected; "
           "learned = the one new fact that output showed (not a summary of earlier work); next = the one concrete action "
           "to take now." if v2 else
           "[harness] Think in JSON: known = what the latest results showed (facts only), next = the one concrete action to take now.")
    note = (f" reasoning = your reasoning or plan, in at most {free} characters." if free else "")
    if stuck and free:
        b["messages"][-1]["content"] += note
    if not stuck:
        b["messages"] = b["messages"] + [{"role": "user", "content": (facts + "\n\n" if facts else "") + ask + note}]
        b.update(max_tokens=think_tokens(with_free(with_caps(TYPED_THINK2 if v2 else TYPED_THINK), free, "last_result" if v2 else None)), tool_choice="none", response_format={"type": "json_schema", "json_schema": {
            "name": "think", "strict": True, "schema": with_free(with_caps(TYPED_THINK2 if v2 else TYPED_THINK), free, "last_result" if v2 else None)}})
    req = urllib.request.Request(base.API, json.dumps(b).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + base.API_KEY})
    with urllib.request.urlopen(req, timeout=300) as r:
        txt = json.load(r)["choices"][0]["message"]["content"]
    # the grammar allows any whitespace; a run of blank lines can reach max_tokens and leave the JSON unclosed (cycle 11:
    # 8 of 233 typed thinks), so the two fields are read with a pattern, not json.loads
    keys = (("failing", "assumption", "next") if stuck else ("last_result", "learned", "next") if v2 else ("known", "next")) \
        + (("reasoning",) if free else ())
    f = {k: re.search(r'"%s"\s*:\s*"((?:[^"\\]|\\.)*)' % k, txt) for k in keys}
    f = {k: json.loads('"' + v.group(1) + '"', strict=False) if v else "" for k, v in f.items()}
    shown = re.findall(r"^(\S+:\d+)$", facts, re.M)
    tail = f"\n(harness facts shown: {', '.join(shown)})" if shown else ""  # logged with the thought, and tells the model
    if free and f.get("reasoning"):
        tail = f"\nReasoning: {f['reasoning']}" + tail
    if stuck:
        return tail.join([f"Last result: stuck. Failing: {f['failing']} Doubtful assumption: {f['assumption']}\nNext: {f['next']}", ""])
    if v2:
        return f"Last result: {f['last_result']}. Learned: {f['learned']}\nNext: {f['next']}" + tail
    return f"Known: {f['known']}\nNext: {f['next']}"


THINK_BLOCKED = "(not run: think is not offered at this step)"


def chat_stream(messages, tools, max_tokens=2048, temperature=0.3, extra=None, think_stop=None, typed=False, fuse=False, judge=False,
                workdir=None):
    """v7n: a think that was left out of the tool list is still called (vLLM 0.31 XPU constrains neither tool names
    under "auto" nor a tool call at all under "required": it answered in plain text, 10-24). Such a call is stopped as
    its name streams in and the step is sampled again, up to 3 times; then it comes back as THINK_BLOCKED."""
    for _ in range(3):
        ch = _chat_stream_once(messages, tools, max_tokens, temperature, extra, think_stop, typed, workdir)
        if ch["finish_reason"] != "think_blocked":
            break
    else:
        if fuse:
            # cycle 24 tax_round (THINK_GAP=2): a think chosen 3 times while not offered came back blocked 5 steps in a
            # row; one that insistent gets its typed think, fused with an action, instead of an empty step
            ch = _chat_stream_once(messages, tools + [THINK_TOOL], max_tokens, temperature, extra, think_stop, typed, workdir)
    tc0 = (ch["message"].get("tool_calls") or [{}])[0]
    if judge and tc0.get("function", {}).get("name") == "think":
        try:
            a = json.loads(tc0["function"]["arguments"])
            body = {"model": base.MODEL, "messages": [{k: v for k, v in m.items() if k != "notes_len"} for m in messages],
                    "tools": tools, "chat_template_kwargs": {"enable_thinking": base.THINK}}
            res = judge_last(body)
            prev = [t for t in earlier_thoughts(messages) if t.startswith("Last result: ")][-2:]
            bad = ("Last result: error", "Last result: unexpected")
            th = f"Last result: {res}. " + str(a.get("thought", ""))
            if res in ("error", "unexpected") and len(prev) == 2 and all(t.startswith(bad) for t in prev) \
                    and THINK_STUCK not in prev[-1]:
                th += THINK_STUCK
            tc0["function"]["arguments"] = json.dumps({"thought": th}, ensure_ascii=False)
        except Exception:
            pass
    if fuse and ch["finish_reason"] == "think_typed":
        # v7o: think and act in one step. A typed think on its own was a free step and was called 10+ times in a row
        # (v7n, cycles 11-12); here the action is asked for at once, with the thought in context and no think tool
        tc = ch["message"]["tool_calls"][0]
        more = messages + [{"role": "assistant", "content": "", "tool_calls": [tc]},
                           {"role": "tool", "tool_call_id": tc.get("id", ""), "content": "ok"}]
        # the action request is not typed: there a long text or a thought leak was turned into another typed think,
        # dropped as a think, and the step came back with no action (cycle 27 three_fix: 10 think-only steps)
        for _ in range(2):
            act = chat_stream(more, [t for t in tools if t["function"]["name"] != "think"], max_tokens, temperature, extra,
                              think_stop, False, workdir=workdir)
            calls = [c for c in act["message"].get("tool_calls") or [] if c["function"]["name"] != "think"]
            if calls:
                break
        ch = {"message": {"role": "assistant", "content": act["message"].get("content") or "", "tool_calls": [tc] + calls},
              "finish_reason": "think_fused" if calls else "think_typed", "tok": act.get("tok"), "rs": act.get("rs")}
    return ch


def _chat_stream_once(messages, tools, max_tokens=2048, temperature=0.3, extra=None, think_stop=None, typed=False, workdir=None):
    """base.chat, streamed: a think call is cut off once its arguments pass THINK_ABORT characters (closing the
    stream makes vLLM abort the request). v7y's written reminder was ignored: thoughts stayed 2000-9000 characters
    and 31-33 s per call (10-23). Returns a choice dict like base.chat."""
    import urllib.request, urllib.error
    messages = [{k: v for k, v in m.items() if k != "notes_len"} for m in messages]
    body = {"model": base.MODEL, "messages": messages, "tools": tools, "max_tokens": max_tokens, "temperature": temperature,
            "chat_template_kwargs": {"enable_thinking": base.THINK}, "stream": True,
            "stream_options": {"include_usage": True}, **(extra or {})}
    req = urllib.request.Request(base.API, json.dumps(body).encode(),
                                 {"Content-Type": "application/json", "Authorization": "Bearer " + base.API_KEY})
    content, calls, finish, reasoning, usage, hidden = "", {}, None, 0, {}, 0
    limit, probe = (2000, 400) if think_stop else (THINK_ABORT, None)
    try:
        r = urllib.request.urlopen(req, timeout=900)
    except urllib.error.HTTPError as e:
        msg = e.read().decode(errors="replace")
        if e.code == 500 and "tool call" in msg:
            raise base.BrokenToolCall(msg[:300])
        if e.code == 400 and "context" in msg:
            raise base.ContextFull(msg[:300])
        raise
    with r:
        for line in r:
            if not line.startswith(b"data: {"):
                continue
            j = json.loads(line[6:])
            usage = j.get("usage") or usage
            ch = (j.get("choices") or [{}])[0]
            d = ch.get("delta") or {}
            content += d.get("content") or ""
            # cycle 20 tax_round: 4096 tokens with no content, thought or call (a malformed call held back by the parser)
            hidden = hidden + 1 if not (d.get("content") or d.get("tool_calls") or d.get("reasoning_content") or d.get("reasoning")) else 0
            if hidden > 1200:
                r.close()
                raise base.BrokenToolCall("1200 chunks with nothing visible (a call the parser held back)")
            # thoughts the reasoning parser moved out of content (thinking is off, but a "<|channel>thought" can
            # still come): counted so slow steps can be told apart from queueing
            reasoning += len(d.get("reasoning_content") or d.get("reasoning") or "")
            # 10-24 cycle 18 cad_wheel: content "thought\n" + 8175 characters of thought channel, 4096 tokens, no call,
            # 71 s. A typed profile turns it into a typed think (fused with the action by chat_stream); others cut it
            if typed and len(content) > 300 and not calls:
                # cycle 23 lru_ttl: "<think>\n..." written as plain text 7 steps in a row, each cut and answered "plain text
                # is not run"; with a typed think, long plain text is an intent to think: same path as the thought leak
                reasoning = 10 ** 6
            elif len(content) > CONTENT_ABORT and not calls:
                # cycle 19 browser_fix: a whole script written as plain text, 4096 tokens and 75 s, none of it saved
                r.close()
                content = content[:600] + TEXT_CUT
                finish = "content_abort"
                break
            if reasoning > (300 if typed else THINK_ABORT) and not calls:
                r.close()
                if typed:
                    calls[0] = {"id": "leak%d" % int(time.time() * 1000), "type": "function",
                                "function": {"name": "think", "arguments": ""}}
                    try:
                        thought = typed_think(body, workdir)
                    except Exception as e:
                        thought = f"(typed think failed: {e})"[:200]
                    calls[0]["function"]["arguments"] = json.dumps({"thought": thought}, ensure_ascii=False)
                    finish = "think_typed"
                else:
                    finish = "think_abort"
                content = ""
                break
            for tc in d.get("tool_calls") or []:
                c = calls.setdefault(tc.get("index", 0), {"id": "", "type": "function", "function": {"name": "", "arguments": ""}})
                c["id"] = tc.get("id") or c["id"]
                f = tc.get("function") or {}
                c["function"]["name"] += f.get("name") or ""
                c["function"]["arguments"] += f.get("arguments") or ""
                n = len(c["function"]["arguments"])
                if typed and c["function"]["name"] == "think" and not any(t["function"]["name"] == "think" for t in tools):
                    r.close()
                    c["function"]["arguments"] = json.dumps({"thought": THINK_BLOCKED})
                    finish = "think_blocked"
                    break
                if typed and c["function"]["name"] == "think":
                    r.close()
                    try:
                        thought = typed_think(body, workdir)
                    except Exception as e:  # a failed typed call must not end the step: keep it as an empty thought
                        thought = f"(typed think failed: {e})"[:200]
                    c["function"]["arguments"] = json.dumps({"thought": thought}, ensure_ascii=False)
                    finish = "think_typed"
                    break
                if (EDIT3 and c["function"]["name"] in ("write_file", "edit_file") and n > 2000
                        and n // 300 != (n - len(f.get("arguments") or "")) // 300):
                    # cycle 39 VBA tasks: 2-3 write_file calls per run cut at 4096 tokens (~150 s each) after the model
                    # started reasoning inside code comments; stop as soon as 25 lines in a row are comments (15 hit a CAD
                    # model's header that listed the part's dimensions, cycle 40)
                    # blank lines between the comments do not break the run (cycle 41 db_migrate: 16531 chars of comments
                    # with blank lines in between went to max_tokens); 6 identical lines in a row is a loop (browser_export:
                    # "# We'll try to find the element..." repeated until 18838 chars). The comment run counts only past 6000
                    # chars: shorter files may carry a block of the VBA they port as comments (cycle 42 vba_sales, 2422 chars)
                    tail_lines = [x for x in c["function"]["arguments"].split("\\n")[-60:-1] if x.strip()][-25:]
                    rep = len(tail_lines) >= 6 and len({x.strip() for x in tail_lines[-6:]}) == 1 and len(tail_lines[-1].strip()) >= 15  # not "}" x6
                    # reasoning written as plain prose in the file (cycle 47/48: "Let's start implementing. I'll first..." to
                    # 14.5K chars): 15 sentence-like lines in a row past 6000 chars
                    prose = lambda x: (re.match(r"\s*[A-Z][a-z']+(\s+[A-Za-z0-9'`,.;:()/-]+){3,}\s*$", x)
                                       and not re.search(r"[=\[\]{}<>]|\b(def|class|return|import|lambda|self)\b", x))
                    rep = rep or (n > 6000 and len(tail_lines) >= 15 and all(prose(x) for x in tail_lines[-15:]))
                    if rep or (n > 6000 and len(tail_lines) == 25 and all(re.match(r"\s*(#(?!!)|//|'|--|/\*|\*)", x)
                                                            and not re.match(r"\s*'[^']*'\s*[:,)\]]", x) for x in tail_lines)):
                        r.close()
                        raise base.BrokenToolCall("comment reasoning: " + ("the same line 6 times in a row" if rep else
                                                  "25 comment lines in a row") + " inside "
                                                  + c["function"]["name"] + f" ({n} chars) last: "
                                                  + " | ".join(x.strip()[:60] for x in tail_lines[-3:]))
                if c["function"]["name"] == "think" and (n > limit or (probe and n > probe)):
                    raw = c["function"]["arguments"]
                    try:
                        text = json.loads(raw + '"}')["thought"]
                    except (ValueError, KeyError, TypeError):
                        text = raw.split(":", 1)[-1].strip(' "')
                    if n <= limit:  # v7m: ask Jev every 300 characters; cut only once the next action is decided
                        probe = n + 300
                        if not think_stop(text):
                            continue
                    c["function"]["arguments"] = json.dumps({"thought": text + THINK_CUT}, ensure_ascii=False)
                    finish = "think_abort"
                    break
            if finish in ("think_abort", "think_typed", "think_blocked"):
                break
            finish = ch.get("finish_reason") or finish
    if finish == "length" and (calls or not content.strip()):
        # a call cut off at max_tokens: the same BrokenToolCall as base.chat gets as HTTP 500 from llama-server, so the
        # "storm" handling answers it (cycle 18: reasoning moved into code comments, write_file cut at 4096 tokens 3x)
        # name, length and tail of the cut call are logged so a repetition can be told from a really long file
        arg = calls[min(calls)]["function"].get("arguments", "") if calls else ""
        raise base.BrokenToolCall(f"cut off at max_tokens: {calls[min(calls)]['function']['name'] if calls else 'nothing visible'}"
                                  + (f" ({len(arg)} chars) tail: {arg[-160:]!r}" if arg else ""))
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = [calls[i] for i in sorted(calls)]
    return {"message": msg, "finish_reason": finish, "tok": usage.get("completion_tokens"), "rs": reasoning}


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
    # v7p: v7e plus the playbooks and lessons mined from past trajectories (playbook.py, docs/lessons-v8.json)
    "v7p": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "playbook"},
    # v7s: v7e plus forced notes: before every action the model must fill fixed fields (JSON grammar), see slot_notes()
    "v7s": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "slots"},
    # v7t: v7s with typed notes: mostly choices (finding kind from the failure taxonomy, files from the workspace), few tokens
    "v7t": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "slots", "slots_typed"},
    # v7u: v7t plus harness checks of the notes against its own record (contradictions, re-reads, finish without tests)
    "v7u": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "slots", "slots_typed",
            "slots_check"},
    # v7x: v7e plus only the harness fixes found while building v8u (no notes): no chmod of inputs, PYTHONPATH, end guard,
    #      inputs restored at the end, spec test as a hard finish gate, file facts each step, stepwise compaction
    "v7x": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes"},
    # v7z: v7x plus an independent auditor after an accepted finish (fresh context, disposable copy, runs real checks;
    #      each reported failure is confirmed by a fast boolean judgment before it is sent back)
    # v7r: v7x plus the requirement checklist (extracted once from the task and docs) shown at the start and once at
    #      the first accepted finish; no audit gate (v7z's 26B-written checks flagged ~50% of the checks on correct solutions)
    "v7r": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "reqs"},
    # v7q: v7x plus an evidence gate at the first accepted finish: the harness collects facts (evidence.py, no model),
    #      a fast judgment per extracted requirement asks decidable / violated / consistent; only agreeing violations go back
    "v7q": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate"},
    # v7w: v7q plus write_dedupe (refuse an identical write_file to the same file within 10 steps)
    # and text_finish (a second text-only reply in a row goes through the finish gate) and midfacts (evidence facts at
    # steps 30 and 55); run it with EV_GENERATORS=1 EV_DIFFLINE=1
    "v7w": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts"},
    # v7k: v7q without the think tool (10-23 vLLM cycles: think was 55% of the model's time, 17 s per call)
    "v7k": {"repeat_result", "storm", "cache", "incontext", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate"},
    # v7y: v7w plus think_cap (a think over 1200 characters is answered with a reminder and cut in the history)
    "v7y": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_cap"},
    # v7a: v7w plus think_abort (the think call's stream is closed at THINK_ABORT characters)
    "v7a": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_abort"},
    # v7m: v7w plus think_jev (streamed; Jev asked every 300 characters whether the next action is decided; hard cut at 2000)
    "v7m": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_jev"},
    # v7n: v7w plus think_typed (a think call becomes a schema-limited {known, next}, Jev-style; ~1.5 s)
    "v7n": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_typed"},
    # v7o: v7w plus think_fuse (a think becomes a typed {known, next} and the action is asked for in the same step)
    "v7o": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_fuse"},
    # v7v: v7a (free think cut at 1000 characters) plus think_judge: each think carries a Jev-typed last_result, and
    # three error/unexpected in a row get a "name the shared assumption" answer (10-24 cycles 19-20: v7a 8/12 vs
    # the all-typed v7o schema 3 5/12, whose 200-character thinks could not hold a plan)
    "v7v": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_abort", "think_judge"},
    # v7p2: v7o (schema 6 typed think) plus verdict_act: the Jev verdict restricts the next step's tools
    "v7p2": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "evgate",
            "write_dedupe", "text_finish", "midfacts", "think_fuse", "verdict_act"},
    "v7z": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "fixes", "audit"},
    # v8u: one loop instead of overlapping mechanisms: the typed, checked notes replace the think and todo tools
    #      (the checklist is written in the first notes and ticked off by choice) and the stagnation nudge (shown as facts)
    "v8u": {"repeat_result", "storm", "cache", "incontext", "v6b", "spec", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "protect_inputs", "hard_tests", "read_window", "slots", "slots_typed", "slots_check",
            "unified"},
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
    # v8c: v7e for CAD tasks (CadQuery rules C1-C5, view_image, the part must build into one valid solid at finish)
    "v8c": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act", "cad"},
    # v7g: v7e with a 120-step budget
    "v7g": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps120",
            "semantic_repeat", "v7b_rules", "stagnation", "protect_inputs", "hard_tests", "read_window", "force_act"},
    "v7c": {"repeat_result", "storm", "cache", "incontext", "think", "v6b", "spec", "think_limit", "restore_inputs", "judge_inputs", "steps80",
            "semantic_repeat", "v7b_rules", "stagnation"},
}


def feats(profile):
    # FEATS_OFF="spec,think" (env) drops features from the profile, for experiments that remove a mechanism
    off = {x for x in os.environ.get("FEATS_OFF", "").replace("/", ",").split(",") if x}
    return FEATURES.get(profile, FEATURES.get(profile.rstrip("abcdefghijklmnopqrstuvwxyz-0123456789"), set())) - off


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
        self.files_snap = None   # file hashes after the previous step
        self.todo_only = 0       # consecutive steps that only called todo (v7f+)
        self.pending_image = None  # image requested with view_image, attached after the tool results
        self.cad = False         # CAD task: the part must build before finish
        self.cad_numbers_checked = False
        self.cad_image_shown = False
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
        self.rec = {"read": {}, "step": 0, "edit_step": 0, "test_step": -1, "test_ok": False}  # facts for check_notes()
        self.finish_tries = 0
        self.judge_log = []
        self.hot = 0
        self.audits = 0
        self.reqs = None
        self.log = None
        self.seed_dir = None


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


CHECK_CMD = re.compile(r"unittest|pytest|spec_test|test_\w+\.py|cadtool|python3 -m \w+")
SERVER_CMD = re.compile(r"(^|[\s/])(server|app)\.py\b|&\s*$|&\s*;|\bnohup\b|serve_forever|http\.server")


def autocheck(box, st, name, a, obs, log):
    """THINK_AUTOCHECK=1: the harness re-runs the agent's latest check command after every successful edit, on a fresh
    copy of /work, and adds its output to the edit's result, so an edit step has facts too (schema 6: 60% of typed
    thinks came right after an edit and had nothing to compare their expectation with). 10-24: 93% of 1541 edits had
    an earlier check command (spec_test 914, unittest 129, the task's own command, cadtool); median run 0.2 s."""
    if name == "bash":
        cmd = str(a.get("command", ""))
        if CHECK_CMD.search(cmd) and not SERVER_CMD.search(cmd) and len(cmd) < 400:
            st.last_check = cmd   # servers are left out: run twice they collide on the port (cycle 29 browser_export)
        return obs
    if name not in ("write_file", "edit_file") or obs.startswith("error") or not getattr(st, "last_check", None):
        return obs
    code, out, err = box.sh("rm -rf /tmp/ac && cp -a /work /tmp/ac && cd /tmp/ac && export PYTHONPATH=/tmp/ac && "
                            + st.last_check, timeout=60)
    log({"autocheck": st.last_check[:200], "code": code})
    return (obs + f"\n[harness] After this edit the harness re-ran your last check on a fresh copy: `{st.last_check}`\n"
            + base.clip(f"exit code: {code}\n--- stdout ---\n{out}\n--- stderr ---\n{err}".strip(), 1500))


def run_tool(box, workdir, st, name, args):
    if name == "view_image":
        p = os.path.join(workdir, base.safe_path(args["path"]))
        if not os.path.exists(p):
            return f"error: {args['path']} does not exist"
        st.pending_image = p
        return f"{args['path']} is shown in the next message."
    if name == "think":
        st.thinks += 1
        n = len(str(args.get("thought", "")))
        if str(args.get("thought", "")).endswith(THINK_STUCK):
            # v7v: the Jev-typed judgment said error/unexpected three times in a row
            return ("ok. [harness] Three results in a row went wrong. Before the next try: name the assumption your "
                    "last tries share, then test that assumption or take a different route. Do not repeat a failed try.")
        if args.get("thought") == THINK_BLOCKED:
            st.thinks -= 1
            return ("error: [harness] think is not available right after a think. Act now: call bash, read_file, "
                    "write_file or edit_file (or finish).")
        if str(args.get("thought", "")).endswith(THINK_CUT):
            # v7a: the stream was closed at THINK_ABORT characters
            return ("ok. [harness] The thought was cut off at the length limit. Do not continue it in another think: "
                    "act now on what you have, with one tool call.")
        if "think_cap" in getattr(st, "feats", ()) and n > 1200:
            # v7y: one think of 3000+ tokens took 75-107 s on vLLM (10-23 html_fix, vba_text ran out of time)
            return (f"ok. [harness] That thought was {n} characters; a long thought takes minutes to write. Keep each "
                    "think under 600 characters: what you now know, and the one thing you will do next.")
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
    if name in ("write_file", "edit_file") and re.search(r"\[\d+ chars, elided", str(args.get("content", "")) + str(args.get("new_text", ""))):
        # v8u price_cache: the model copied the elision placeholder of an old call and wrote it into its test
        return ("error: you copied the placeholder '[... chars, elided ...]' of an older call. Nothing was written. "
                "Write the real content (read the file first if you need its current text).")
    if (name == "write_file" and os.environ.get("EDIT3") == "1" and str(args.get("content", "")).strip() == "@kept"
            and getattr(st, "kept", None)):
        args = dict(args, content=st.kept)
        st.kept = None
    if os.environ.get("EDIT2") == "1":
        # cycle 36 semver_sort: vsort/parse.py rewritten 8 times in a row (steps 14-21) with no run in between
        wr = st.__dict__.setdefault("writes_norun", {})
        if name == "bash":
            wr.clear()
        elif name == "write_file" and args.get("mode") != "append":   # a file written in parts is one write
            rel0 = str(args.get("path", ""))
            if wr.get(rel0, 0) >= 2:
                return (f"error: not written. You already rewrote {rel0} {wr[rel0]} times without running anything. "
                        f"Run a check first (the task's command or your test) to see what the last version does, "
                        f"then change only what that output shows is wrong.")
            wr[rel0] = wr.get(rel0, 0) + 1
    if name == "write_file":
        rel = base.safe_path(args["path"])
        p = os.path.join(workdir, rel)
        if {"unified", "fixes"} & set(getattr(st, "feats", ())) and args.get("mode") != "append" and os.path.exists(p):
            try:
                same = open(p, encoding="utf-8").read() == str(args.get("content", ""))
            except (OSError, UnicodeDecodeError):
                same = False
            if same:  # v8u billing: the same 1196 chars written 5x (the repeat record is reset by every change)
                return f"error: {rel} already has exactly this content; nothing changed."
        os.makedirs(os.path.dirname(p) or workdir, exist_ok=True)
        mode = "a" if args.get("mode") == "append" else "w"
        prev = open(p, encoding="utf-8", errors="replace").read() if os.path.exists(p) else None
        st.changed = mode == "a" or prev != args["content"]
        nudge = ""
        if EDIT3 and prev and mode == "w" and rel.endswith(".py"):
            # cycle 48 h_sqlite_timetrack_repo: a whole-file rewrite silently dropped daily_minutes() -> AttributeError
            gone = sorted(set(re.findall(r"^(?:async\s+)?(?:def|class)\s+(\w+)", prev, re.M))
                          - set(re.findall(r"^(?:async\s+)?(?:def|class)\s+(\w+)", str(args.get("content", "")), re.M)))
            if gone:
                nudge += (f"\n[harness] This rewrite removed {', '.join(gone[:8])} that the previous version of {rel} "
                          f"defined. If anything still uses them (other modules, tests, the task), put them back.")
        if os.environ.get("EDIT2") == "1" and prev and mode == "w" and not rel.startswith(".agent/"):
            import difflib   # measure: how much of a whole-file rewrite actually changed
            a, b = prev.split("\n"), str(args["content"]).split("\n")
            same = sum(x.size for x in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
            if len(b) >= 40 and len(b) - same <= 0.2 * len(b):
                # cycle 36 semver_sort: 93 lines rewritten to change 1, 94 for 7 (~30 s of decoding each at 4 jobs/card)
                nudge = (f"\n[harness] This rewrite of {len(b)} lines changed only {len(b) - same}. For a change this "
                         f"small use edit_file with a short old_text (1-5 lines): it is much faster than rewriting the file.")
            try:
                with open(os.path.join(os.path.dirname(workdir), "edit_fail.jsonl"), "a", encoding="utf-8") as f:
                    f.write(json.dumps({"kind": "rewrite", "path": rel, "lines": len(b), "changed": len(b) - same}) + "\n")
            except OSError:
                pass
        with open(p, mode, encoding="utf-8") as f:
            f.write(args["content"])
        msg = f"{'appended' if mode == 'a' else 'wrote'} {len(args['content'])} chars to {rel}" + nudge + st.__dict__.pop("path_note", "")
        msg += lint_note(st, workdir, rel)
        err = py_check(box, rel)
        return msg + (f"\nwarning: {rel} does not compile yet:\n{err}" if err else "")
    if name == "edit_file":
        rel = base.safe_path(args["path"])
        p = os.path.join(workdir, rel)
        with open(p, encoding="utf-8") as f:
            before = f.read()
        old, new = args["old_text"], args["new_text"]
        edit2 = os.environ.get("EDIT2") == "1"
        if edit2:
            old, new = strip_lnum(old), strip_lnum(new)
        if old == new:
            if edit2:
                edit_fail_log(workdir, rel, args, before, "identical")
            return "error: old_text and new_text are identical, so nothing changed. Decide what the code should become and put that in new_text."
        n = before.count(old)
        after = before.replace(old, new) if n == 1 else (base.fuzzy_replace(before, old, new) if n == 0 else None)
        note = ""
        if after is None and n == 0 and edit2:
            # v7o 10-24: 377 of 1527 edits failed with "old_text not found" (long blocks retyped from memory, the middle
            # off); then "rewrite the whole file" made the model emit whole files at ~26 tok/s, 191 s per timed-out run
            hit = anchor_replace(before, old, new)
            if hit:
                after, a, b = hit
                note = f" (old_text differed from the file between its first and last line; replaced lines {a}-{b} of the file)"
                edit_fail_log(workdir, rel, args, before, f"anchor {a}-{b}")
        if after is None:
            st.edit_fail[rel] = st.edit_fail.get(rel, 0) + 1
            if edit2:
                edit_fail_log(workdir, rel, args, before, "multi" if n > 1 else "notfound")
            region = region_text(before, old) if edit2 and n == 0 else None
            hint = (f"error: old_text found {n} times (must be exactly 1); include more surrounding lines." if n > 1
                    else "error: old_text not found. " + (region or base.closest_lines(before, old)))
            if st.edit_fail[rel] >= 2 and edit2:
                hint += (f"\n[harness] Editing {rel} failed {st.edit_fail[rel]} times. Use a SHORT old_text: 1-3 lines copied "
                         f"exactly from the text above (without line numbers), not a whole function.")
            elif st.edit_fail[rel] >= 2:
                hint += f"\n[harness] Editing {rel} failed {st.edit_fail[rel]} times. Rewrite the whole file with write_file instead."
            return hint
        if edit2 and after == before:
            # cycle 39 bizdays: the same anchored edit 8x, each answered "edited" though the file already held new_text
            return (f"error: {rel} already contains this new_text, so nothing changed (your earlier edit is in place). "
                    f"Run a check to see what the code does now instead of editing again.")
        st.changed = after != before
        with open(p, "w", encoding="utf-8") as f:
            f.write(after)
        err = py_check(box, rel)
        if err:
            with open(p, "w", encoding="utf-8") as f:
                f.write(before)
            return f"error: the edit made {rel} invalid Python, so it was rolled back:\n{err}"
        st.edit_fail[rel] = 0
        return "edited" + note + lint_note(st, workdir, rel)
    if name == "bash" and {"unified", "fixes"} & set(getattr(st, "feats", ())):
        # the project's own modules import from anywhere (v8u: 1-2 steps per task lost to ModuleNotFoundError)
        args = dict(args, command="export PYTHONPATH=/work${PYTHONPATH:+:$PYTHONPATH}\n" + str(args.get("command", "")))
    if name == "bash" and os.environ.get("FINISH_NUDGE") == "1" and CHECK_CMD.search(str(args.get("command", ""))):
        # without a spec test (FEATS_OFF=spec) the model lost its signal to stop: cycle 43 cad_wheel had the right
        # part at step 6 (volume 102015.1 = expected) and re-ran cadtool 6x unchanged. Same check, same files, same
        # output -> say so and ask for finish or a specific change.
        out = base.run_tool(box, workdir, name, args)
        key, snap = str(args.get("command", "")), snapshot(workdir)
        lc = st.__dict__.setdefault("last_check", {})
        prev = lc.get(key)
        same = prev is not None and prev[0] == snap and re.sub(r"\d+\.\d+s", "", prev[1]) == re.sub(r"\d+\.\d+s", "", out)
        lc[key] = (snap, out, (prev[2] + 1) if same else 0)
        if same:
            out += ("\n[harness] Same files, same command, same result as the last time you ran it. If this result shows "
                    "the task is done, call finish now. Otherwise change one specific thing that this output shows is wrong.")
        return out
    return base.run_tool(box, workdir, name, args)


LNUM = re.compile(r"^ *\d+\| ?")


def strip_lnum(s):
    """drop read_file's '  18| ' prefixes when every non-blank line carries one"""
    ls = s.split("\n")
    if any(l.strip() for l in ls) and all(LNUM.match(l) for l in ls if l.strip()):
        return "\n".join(LNUM.sub("", l, count=1) for l in ls)
    return s


def anchor_replace(s, old, new):
    """EDIT2: old_text whose first and last non-blank lines each occur once in the file, in order, around a block of
    about the same length and mostly the same text -> (new file, first line no, last line no) or None"""
    import difflib
    lines = s.split("\n")
    olds = [l for l in old.strip("\n").split("\n")]
    if len(olds) < 3:
        return None
    # line-level alignment: the first old line is sometimes one the model only remembers (cycle 36 browser_fix: 16 of
    # 18 lines matched, the first did not), so anchor on the matched non-blank lines instead of on the first/last line
    fn, on = [base._norm(l) for l in lines], [base._norm(l) for l in olds]
    sm = difflib.SequenceMatcher(None, on, fn, autojunk=False)
    pairs = [(a + k, b + k) for a, b, size in sm.get_matching_blocks() for k in range(size) if on[a + k]]
    nb = sum(1 for x in on if x)
    if len(pairs) < max(3, 0.7 * nb):
        return None
    oi, i = pairs[0]
    oj, j = pairs[-1]
    if not 0.5 * len(olds) <= j - i + 1 <= 1.5 * len(olds) + 2:
        return None
    # the matched lines must not also fit somewhere else (a repeated block would make the target ambiguous)
    core = [on[a] for a, _ in pairs]
    if sum(1 for k in range(len(fn)) if fn[k] == core[0]) > 1 and sum(1 for k in range(len(fn)) if fn[k] == core[-1]) > 1:
        return None
    # old lines before the first match / after the last one: a misremembered variant of the file's neighbouring line
    # (e.g. timeout(5000) for timeout(3000)) joins the span so it is replaced, not duplicated; otherwise they are lines
    # the model believes are there and new_text brings them in
    sim = lambda x, y: difflib.SequenceMatcher(None, x, y).ratio() >= 0.5
    while oi > 0 and i > 0 and on[oi - 1] and sim(on[oi - 1], fn[i - 1]):
        oi, i = oi - 1, i - 1
    while oj < len(on) - 1 and j < len(fn) - 1 and on[oj + 1] and sim(on[oj + 1], fn[j + 1]):
        oj, j = oj + 1, j + 1
    # file lines in the span that old_text has no counterpart for (not equal, not a close variant) are code the model
    # does not know is there; replacing them deletes it (cycle 37 browser_export: 14 such lines incl. the
    # `detail_btn = ...` assignment went, `detail_btn.click()` stayed -> NameError)
    matched_f = {b for _, b in pairs}
    loose = [x for x in on if x and x not in set(fn[i:j + 1])]
    unknown = [k for k in range(i, j + 1) if fn[k] and k not in matched_f
               and not any(difflib.SequenceMatcher(None, fn[k], x).ratio() >= 0.75 for x in loose)]
    comment = lambda x: x.startswith(("#", "//", "/*", "*", "<!--", "--", "'''", '"""'))
    # one unknown line of code is enough to break the file (the second browser_export anchor dropped only
    # `detail_btn = ...` plus two comments); unknown comments are tolerated (cycle 37 toposort: 4 commented-out
    # debug prints)
    if any(not comment(fn[k]) for k in unknown):
        return None
    indent = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
    o_indent = olds[oi][: len(olds[oi]) - len(olds[oi].lstrip())]
    new_lines = [indent + l[len(o_indent):] if l.startswith(o_indent) else l for l in new.strip("\n").split("\n")]
    return "\n".join(lines[:i] + new_lines + lines[j + 1:]), i + 1, j + 1


def def_block(s, new):
    """EDIT2: edit_file without old_text whose new_text starts with `def NAME`/`class NAME` (38 v7o calls failed with
    "needs 'old_text'", cycle 37 db_migrate then rewrote whole files) -> that definition's current block in the file,
    when there is exactly one, or None"""
    m = re.match(r"\s*(?:async\s+)?(def|class)\s+(\w+)", new)
    if not m:
        return None
    lines = s.split("\n")
    hits = [i for i, l in enumerate(lines) if re.match(rf"\s*(?:async\s+)?{m.group(1)}\s+{m.group(2)}\b", l)]
    if len(hits) != 1:
        return None
    i = hits[0]   # decorators above stay: new_text starts at def/class, so it does not repeat them
    ind = len(lines[i]) - len(lines[i].lstrip())
    j = hits[0] + 1
    while j < len(lines) and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > ind):
        j += 1
    while j > hits[0] + 1 and not lines[j - 1].strip():
        j -= 1   # trailing blank lines stay
    return "\n".join(lines[i:j])


def region_text(s, old):
    """EDIT2 failed-edit hint: the file's current text of the part old_text was aimed at (found by line alignment),
    so the model can copy it; the plain hint showed only 6 lines around the line most like old_text's first line"""
    import difflib
    lines = s.split("\n")
    fn, on = [base._norm(l) for l in lines], [base._norm(l) for l in old.strip("\n").split("\n")]
    sm = difflib.SequenceMatcher(None, on, fn, autojunk=False)
    hits = [b + k for a, b, size in sm.get_matching_blocks() for k in range(size) if on[a + k]]
    if not hits:
        return None
    i, j = max(0, hits[0] - 2), min(len(lines), hits[-1] + 3)
    if j - i > 60:
        return None
    return (f"Your old_text does not match the file. The file's CURRENT text for that part (lines {i + 1}-{j}) is below "
            f"between the markers; lines in your old_text that differ from it, or that it has and your old_text lacks, "
            f"are why it failed. Copy old_text exactly from it (without line numbers):\n<<<\n"
            + "\n".join(lines[i:j]) + "\n>>>")


def lint_note(st, workdir, rel):
    """LINT=1: the domain sheets (know.py) as checks on the file just written; each finding once per file"""
    if os.environ.get("LINT") != "1" or not getattr(st, "know_keys", None):
        return ""
    try:
        import know
        text = open(os.path.join(workdir, rel), encoding="utf-8", errors="replace").read()
        seen = st.__dict__.setdefault("lint_seen", set())
        new = [(k, m) for k, m in know.lint(st.know_keys, rel, text, root=workdir) if (k, rel) not in seen]
        seen.update((k, rel) for k, _ in new)
        if st.log and new:
            st.log({"lint": [k for k, _ in new], "path": rel})
        return "".join(f"\n[harness] check {rel}: {m}" for _, m in new)
    except Exception as e:
        return ""


def edit_fail_log(workdir, rel, args, before, kind):
    """full failed edits (log.jsonl clips call arguments at 1500 chars) for offline study"""
    try:
        with open(os.path.join(os.path.dirname(workdir), "edit_fail.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps({"kind": kind, "path": rel, "old": args.get("old_text"), "new": args.get("new_text"),
                                "file": before}, ensure_ascii=False) + "\n")
    except OSError:
        pass


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
        limit = CTX_SOFT_LIMIT // (2 ** int(st.compact))  # chars, so dense data (CSV digits) needs several halvings
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
    imgs = [i for i, m in enumerate(messages) if isinstance(m.get("content"), list)]
    for i, m in enumerate(messages):
        if i in imgs[:-1]:
            m = dict(m, content=" ".join(p.get("text", "") for p in m["content"] if p.get("type") == "text") + " [image no longer shown]")
        if m["role"] == "tool" and i in hide and len(m["content"]) > 200:
            m = dict(m, content=f"[older output elided: {one_line(m['content'])}; {m['content'].count(chr(10)) + 1} lines]")
        elif m.get("tool_calls") and i in hide:
            m = dict(m, tool_calls=[elide_args(c) for c in m["tool_calls"]])
        out.append(m)
    tv = todo_view(st)
    if "fixes" in getattr(st, "feats", ()):
        ff = file_facts(st, restore_hint=False)
        tv = (tv + "\n" if tv else "") + "[harness] " + "\n".join(ff)
    if tv and out[-1]["role"] == "tool":
        out.append({"role": "user", "content": tv})
    return out


SLOT_SCHEMA = {"type": "object", "properties": {k: {"type": "string", "maxLength": 400} for k in
               ("last_result", "still_missing", "tried_before", "next_action")},
               "required": ["last_result", "still_missing", "tried_before", "next_action"]}


FINDINGS = ["nothing new", "name or key mismatch", "wrong condition or edge case", "wrong calculation or rounding",
            "stale state or cache", "wrong order of steps (an event or call happens too early or too late)", "requirement not yet done", "input format differs from assumed", "path or import problem",
            "test or environment problem", "my change broke something", "everything required is done", "other"]
NEXT = ["read code", "search", "write test", "edit code", "run test", "run program", "finish"]


def action_choices(files, st, msgs):
    """v8u: the next action is one choice; what the record says makes no sense is not offered at all (grammar), instead of
    being rejected afterwards (rejections cost a model call each and the action ignored them: 17 re-reads of one file)."""
    r = st.rec
    hashes = r.get("hashes") or {}
    vis = visible_reads(msgs)
    acts, tail = [], []  # doing is listed before looking: with the reads first, 48% of all choices were reads
    blocked = r.get("edit_block", set())  # an edit there changed nothing: read the file again before editing it
    if r.get("reads_row", 0) < 4:
        tail += [f"read {f}" for f in files
                 if f in blocked or not (f in vis and f in r["read"] and r["read"][f] == hashes.get(f))]
    tail.append("search")
    if st.todo:
        # a test that was just written must be run before it is rewritten (v8u cmd_registry: rewritten 4x unrun)
        # ...and after two rewrites without any change to the code itself, the code is next (v8u billing: test-only loop)
        acts += ["create new file"]  # v8u cmd_registry: a new module could only be chosen as "write test"
        acts += (["write test"] if r.get("wrote_test_step", -1) <= r["test_step"] and r.get("test_rewrites", 0) < 2 else []) + [f"edit {f}" for f in files if f not in getattr(st, "protected", set())
                                  and not f.startswith(".agent/orig") and f not in blocked]
        # after a failed edit the whole file may be rewritten (v8u billing: no choice for it, 6 blocked write_file calls)
        acts += [f"rewrite {f}" for f in sorted(blocked) if f in files and f not in getattr(st, "protected", set())]
        # a test re-run with no file changed since gives the same result (v8u billing: 5 identical runs)
        acts += ["run test"] if r["test_step"] < 0 or r["test_step"] < r["edit_step"] else []
        # the same run was refused as a repeat: running is not offered again until a file changes
        # (v8u price_cache: with "run test" withheld it re-ran its test 4x as "run program")
        acts += ["run program"] if not r.get("rerun_refused") else []
        if r.get("same_runs", 0) >= 2:  # ran twice with no code change: change the code before running again
            acts = [a for a in acts if a not in ("run test", "run program")]
        if r["test_ok"] and r["test_step"] >= r["edit_step"] and r["test_step"] >= 0:
            acts.append("finish")
        # a provided file the model changed can be put back exactly (v8u billing: 8 attempts to retype dates.py from memory)
        acts += [f"restore {p}" for p, b in sorted(st.seed_bytes.items())
                 if not p.startswith(".agent/") and hashes.get(p) not in (None, hashlib.sha1(b).hexdigest())]
    acts = acts + tail
    st.acts = acts
    return acts


def allowed_call(st, calls):
    """Is the call one of the offered actions, whatever the notes said? (then a mislabelled choice is not blocked)"""
    acts = set(getattr(st, "acts", ()))
    c = calls[0]["function"]
    try:
        a = json.loads(c["arguments"] or "{}")
        a = a if isinstance(a, dict) else {}
    except ValueError:
        return False
    name = c["name"]
    path = base.safe_path(str(a.get("path", ""))) if a.get("path") else None
    if name == "read_file":
        return f"read {path}" in acts or f"edit {path}" in acts
    if name in ("write_file", "edit_file"):
        exists = path in (st.rec.get("hashes") or {})
        if exists:
            return f"edit {path}" in acts or (name == "write_file" and f"rewrite {path}" in acts)
        return "create new file" in acts or "write test" in acts
    if name == "finish":
        return "finish" in acts
    if name == "bash":
        return bool(acts & {"search", "run test", "run program"})
    return True


def typed_schema(workdir, st=None, msgs=()):
    files = sorted(os.path.relpath(os.path.join(r, f), workdir) for r, _, fs in os.walk(workdir) for f in fs
                   if "__pycache__" not in r and "/.agent/orig" not in r + "/")[:80]
    if st is not None and "unified" in st.feats:
        acts = action_choices(files, st, msgs)
        if not st.todo:  # first notes: the checklist that replaces the todo tool
            return {"type": "object", "properties": {
                "checklist": {"type": "array", "minItems": 1, "maxItems": 12, "items": {"type": "string", "maxLength": 160}},
                "note": {"type": "string", "maxLength": 140}, "action": {"enum": acts}},
                "required": ["checklist", "note", "action"]}
        open_items = [i["text"] for i in st.todo if i["status"] != "done"]
        return {"type": "object", "properties": {
            "finding": {"enum": FINDINGS}, "completed": {"enum": open_items + ["none"]},
            "note": {"type": "string", "maxLength": 140}, "action": {"enum": acts}},
            "required": ["finding", "completed", "note", "action"]}
    files = files + ["none"]
    return {"type": "object", "properties": {
        "learned_new": {"type": "boolean"},
        "finding": {"enum": FINDINGS},
        "where": {"enum": files},
        "repeating": {"type": "boolean"},
        "next": {"enum": NEXT},
        "target": {"enum": files},
        "note": {"type": "string", "maxLength": 140}},
        "required": ["learned_new", "finding", "where", "repeating", "next", "target", "note"]}


def track(st, name, a, obs):
    """Facts the harness checks the model's notes against: what was read (and the file's hash then), edits, tests."""
    r = st.rec
    r["step"] += 1
    reading = name == "read_file" or (name == "bash" and re.match(r"\s*(cat|head|tail|sed -n|nl|less)\b", str(a.get("command", ""))))
    r["reads_row"] = r.get("reads_row", 0) + 1 if reading else 0
    hashes = snapshot(st.workdir)
    if name in ("edit_file", "write_file") and a.get("path") and (
            obs.startswith("error: old_text and new_text are identical") or obs.startswith("error: old_text not found")
            or "already has exactly this content" in obs):
        r.setdefault("edit_block", set()).add(base.safe_path(str(a["path"])))  # look again before the next edit there
    if name == "read_file":
        p = base.safe_path(str(a.get("path", "")))
        r["read"][p] = hashes.get(p)
        r.setdefault("edit_block", set()).discard(p)
    if name == "write_file" and obs.startswith("wrote") and a.get("mode") != "append" and a.get("path"):
        # its full content is in the call itself (v8u cmd_registry: registry.py re-read 11x after writing it)
        r["read"][base.safe_path(str(a["path"]))] = hashes.get(base.safe_path(str(a["path"])))
    if name == "write_file" and "test" in str(a.get("path", "")):
        r["wrote_test_step"] = r["step"]
        r["test_rewrites"] = r.get("test_rewrites", 0) + 1
    old = r.get("hashes") or {}
    if any(old.get(p) != h for p, h in hashes.items() if not p.startswith(".agent/") and "test" not in p) and old:
        r["test_rewrites"] = 0  # the code itself changed
    if name == "bash":
        cmd = str(a.get("command", ""))
        for tok in re.split(r"[\s'\"|;<>]+", cmd):
            t = tok[2:] if tok.startswith("./") else tok
            if t in hashes and re.search(r"\b(cat|head|tail|sed -n|less|nl)\b", cmd):
                r["read"][t] = hashes[t]
        # the same run with no code change since: tests that write files into the workspace defeat the repeat check
        # (v8u expense: unittest discover 5x in a row, every run rewrote expenses.json)
        code = tuple(sorted((p, h) for p, h in hashes.items() if p.endswith(".py") and not p.startswith(".agent/")))
        key = (cmd.strip(), hash(code))
        r["same_runs"] = r.get("same_runs", 0) + 1 if key == r.get("last_run") else 1
        r["last_run"] = key
        if re.search(r"test|pytest|unittest|check", cmd):
            r["test_step"], r["test_ok"] = r["step"], obs.startswith("exit code: 0")
            if r["test_ok"] and re.search(r"unittest discover|spec_test", cmd):
                keep = {}
                snapshot(st.workdir, keep)  # the last state whose tests passed, for end_guard()
                st.best = {k: v for k, v in keep.items() if "__pycache__" not in k}
    if hashes != r.get("hashes"):
        if r.get("hashes") is not None and name != "read_file":
            r["edit_step"] = r["step"]
            r["rerun_refused"] = 0
        r["hashes"] = hashes


END_CHECK = ("export PYTHONPATH=/work; (test ! -d tests || python3 -m unittest discover -s tests) && "
             "(test ! -f .agent/spec_test.py || python3 .agent/spec_test.py)")


def end_guard(st, box, log):
    """v8u: never end on a state worse than the last one whose tests passed (v8u footnote: the last edit introduced a
    circular import and the run ended with nothing importable). Restores the passing state if the end state fails."""
    # protected inputs are no longer chmod'ed in v8u, so a bash run can change them (v8u cmd_registry: `python3 -m
    # invtool add ...` wrote data/inventory.csv); the run may end at the step cap without the finish-time restore
    for p in getattr(st, "protected", ()):
        if p in st.seed_bytes:
            with open(os.path.join(st.workdir, p), "wb") as fh:
                fh.write(st.seed_bytes[p])
    if not getattr(st, "best", None):
        return
    code, _, _ = box.sh(END_CHECK, timeout=120)
    if code == 0:
        return
    end = {}
    now = snapshot(st.workdir, end)

    def put(state, current):
        for p in current:
            if p not in state and not p.startswith(".agent/") and "__pycache__" not in p:
                try:
                    os.remove(os.path.join(st.workdir, p))
                except OSError:
                    pass
        for p, b in state.items():
            full = os.path.join(st.workdir, p)
            os.makedirs(os.path.dirname(full) or st.workdir, exist_ok=True)
            with open(full, "wb") as fh:
                fh.write(b)
    put(st.best, now)
    code2, _, _ = box.sh(END_CHECK, timeout=120)
    if code2 != 0:  # the saved state does not pass the full check either: keep what the agent ended with
        put(end, snapshot(st.workdir))
    log({"end_guard": {"end_state_failed": True, "restored": code2 == 0}})


def visible_reads(msgs):
    """Files whose latest read_file output is still shown in full in these messages."""
    ids, seen = {}, set()
    for m in msgs:
        for c in m.get("tool_calls") or []:
            if c["function"]["name"] == "write_file":
                try:
                    wa = json.loads(c["function"]["arguments"] or "{}")
                    wp = base.safe_path(str(wa.get("path", "")))
                    if wa.get("mode") != "append":
                        (seen.discard if re.match(r"\[\d+ chars, elided", str(wa.get("content", ""))) else seen.add)(wp)
                except (ValueError, AttributeError):
                    pass
            if c["function"]["name"] == "read_file":
                try:
                    ids[c.get("id", "")] = base.safe_path(str(json.loads(c["function"]["arguments"] or "{}").get("path", "")))
                except (ValueError, AttributeError):
                    pass
            if c["function"]["name"] == "bash":  # `cat FILE` shows it as well (v8u billing: cat data/subscriptions.csv 4x)
                try:
                    cmd = str(json.loads(c["function"]["arguments"] or "{}").get("command", ""))
                except (ValueError, AttributeError):
                    cmd = ""
                mm = re.fullmatch(r"\s*cat\s+([\w./-]+)\s*", cmd)
                if mm:
                    ids[c.get("id", "")] = base.safe_path(mm.group(1).removeprefix("./"))
        if m["role"] == "tool" and m.get("tool_call_id") in ids:
            p = ids[m["tool_call_id"]]
            if str(m.get("content", "")).startswith("[older output elided"):
                seen.discard(p)
            else:
                seen.add(p)
    return seen


def check_notes(d, msgs, st):
    """Contradictions between the typed notes and the harness's record. Returns a list of problems."""
    r, bad = st.rec, []
    if "unified" in st.feats:
        return bad  # impossible choices are not offered (action_choices); nothing left to reject
    last = str(msgs[-1].get("content") or "") if msgs else ""
    t = d.get("target")
    if r["step"] == 0:  # nothing has run yet: only looking around makes sense
        if d.get("learned_new"):
            bad.append("Nothing has run yet, so learned_new must be false.")
        if d.get("next") not in ("read code", "search"):
            bad.append("Nothing has been read yet. Start by reading the code or searching the project, not by "
                       + str(d.get("next")) + ".")
        return bad
    if d.get("learned_new") and d.get("finding") == "nothing new":
        bad.append("learned_new is true but finding is 'nothing new'.")
    if d.get("learned_new") and "already ran" in last:
        bad.append("Your last action was a repeat that did not run again, so nothing new was learned.")
    if d.get("repeating"):
        bad.append("You said the next action repeats something already tried. Choose a different next action.")
    # re-reading is refused only while the file's last full read is still visible in the context: older outputs are
    # elided (v8u: 16 rejections for files the model could no longer see), but unrestricted re-reads looped (9x pricing.py)
    if d.get("next") == "read code" and t in visible_reads(msgs) and r["read"].get(t) == (r.get("hashes") or {}).get(t):
        bad.append(f"{t} is unchanged and its full content is still shown above. Use it instead of reading it again.")
    if (d.get("finding") == "everything required is done") != (d.get("next") == "finish"):
        bad.append("finding 'everything required is done' and next 'finish' must go together.")
    open_items = [i["text"] for i in st.todo if i["status"] != "done" and i["text"] != d.get("completed")]
    if "unified" in st.feats and d.get("next") == "finish" and open_items:
        bad.append("Checklist items are not done yet: " + "; ".join(open_items[:4]) + ". Finish them (or verify them) first.")
    if d.get("next") == "finish" and (r["test_step"] < r["edit_step"] or not r["test_ok"]):
        bad.append("You have not run the tests successfully since your last change. Run them before finishing.")
    if d.get("next") == "edit code" and t in getattr(st, "protected", set()):
        bad.append(f"{t} is a provided input file; the task does not ask you to change it. Edit the code instead.")
    return bad


def plan_mismatch(d, calls, st_files=None):
    """The action must be the one the notes chose (v7u: rejected notes were rewritten, then ignored)."""
    if not d or not calls:
        return None
    if "action" in d:  # v8u: one combined choice such as "read shop/x.py", "edit shop/x.py", "run test", "finish"
        c = calls[0]["function"]
        name, act = c["name"], str(d["action"])
        if name in ("todo", "think"):
            return None
        try:
            a = json.loads(c["arguments"] or "{}")
        except ValueError:
            return None
        a = a if isinstance(a, dict) else {}
        path = base.safe_path(str(a.get("path", ""))) if a.get("path") else None
        kind, _, f = act.partition(" ")
        if act == "finish":
            ok = name == "finish"
        elif kind == "read":
            ok = (name == "read_file" and path == f) or (name == "bash" and f in str(a.get("command", "")))
        elif kind == "rewrite":
            ok = name == "write_file" and path == f
        elif kind == "edit":
            # reading the file first is part of editing it (v8u footnote: 3 blocked look-before-edit reads)
            ok = (name in ("write_file", "edit_file", "read_file") and path == f) or (name == "bash" and f in str(a.get("command", "")))
        elif act == "search":
            ok = name in ("bash", "read_file")
        elif act in ("write test", "create new file"):
            # bash only when it really writes a file (v8u: "write test" was used to re-run the same test 5x); a test is a
            # file named *test*, a new file must not exist yet (v8u billing: "write test" overwrote billing/proration.py)
            writes = re.search(r"<<|(^|[^2&])>\s*[\w./]|\btee\b|\bcp\b|\bmv\b|\bmkdir\b", str(a.get("command", "")))
            ok = name in ("write_file", "edit_file") or (name == "bash" and bool(writes))
            if ok and path and act == "write test" and "test" not in path:
                return f"you chose 'write test' but wrote {path}, which is not a test file (choose 'edit {path}' for that)"
            if ok and path and act == "create new file" and path in (st_files or ()):
                return f"you chose 'create new file' but {path} already exists (choose 'edit {path}' for that)"
        else:  # run test / run program
            ok = name == "bash"
        return None if ok else f"you chose '{act}' but called {name}" + (f" on {path}" if path else "")
    c = calls[0]["function"]
    name = c["name"]
    try:
        a = json.loads(c["arguments"] or "{}")
    except ValueError:
        return None
    if not isinstance(a, dict) or name in ("todo", "think"):
        return None
    nxt, t = d.get("next"), d.get("target")
    path = base.safe_path(str(a.get("path", ""))) if a.get("path") else None
    # only the kind of action is bound; bash may do anything (heredoc writes, sed edits), reading another file is fine
    want = {"read code": ("read_file", "bash"), "search": ("bash", "read_file"), "write test": ("write_file", "edit_file", "bash"),
            "edit code": ("write_file", "edit_file", "bash"), "run test": ("bash",), "run program": ("bash",), "finish": ("finish",)}
    if name not in want.get(nxt, (name,)):
        return f"your notes chose next '{nxt}' (target {t}), but you called {name}"
    if nxt == "edit code" and path and t not in (None, "none") and path != t:
        return f"your notes chose to edit {t}, but you called {name} on {path}"
    return None


def file_facts(st, restore_hint=True):
    """Facts about the files the harness can state exactly: changed provided files, missing deliverables, lost definitions."""
    r, facts = st.rec, []
    lost = []  # definitions of the provided files that are gone now (v8u billing: add_months deleted, never noticed)
    for p, b in sorted(st.seed_bytes.items()):
        if not p.endswith(".py") or p.startswith(".agent/"):
            continue
        try:
            now = open(os.path.join(st.workdir, p), encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            now = ""
        gone = [n for n in re.findall(r"(?m)^(?:def|class) (\w+)", b.decode("utf-8", "ignore"))
                if not re.search(rf"(?m)^(?:def|class) {n}\b", now)]
        if gone:
            lost.append(f"{p} no longer defines {', '.join(gone[:6])} (the original did)")
    cur = r.get("hashes") or {}
    changed = [p for p, b in sorted(st.seed_bytes.items()) if not p.startswith(".agent/")
               and cur.get(p) != hashlib.sha1(b).hexdigest()]
    # v8u settings_migrate: it kept trying to "restore" tool/scanner.py, which was already identical to the original
    facts.append("Provided files you have changed: " + (", ".join(changed[:10]) if changed else "none")
                 + ". Every other provided file is exactly as given.")
    named = sorted(set(re.findall(r"(?<![\w./-])((?:[\w-]+/)*[\w-]+\.(?:py|md|txt|csv|json|html|toml|ini|cfg|sh))\b",
                                      getattr(st, "task", ""))))
    # a bare name counts as missing only if no file of that name exists anywhere (v8u incident_logs: incident.json)
    present = {f for _, _, fs in os.walk(st.workdir) for f in fs}
    missing = [n for n in named if not os.path.exists(os.path.join(st.workdir, n)) and ("/" in n or n not in present)]
    if missing:  # v8u expense: "write the tests in tests/test_report.py" was never done (checklist cut at 8 items)
        facts.append("Files named in the task that do not exist yet: " + ", ".join(missing[:6])
                     + " (create them unless the task says they should be removed or are only examples).")
    if lost:
        facts.append("WARNING: " + "; ".join(lost[:4]) + ". Unless the task asks to remove them, put them back "
                     + ("(edit the file, or choose restore to get the original back)." if restore_hint else "(edit the file)."))
    return facts


def slot_notes(msgs, st, offered, temp):
    """Bare v8 runs ran the same command 51-71 times; a playbook rule against it was ignored. Before every action the
    model has to write these fields (enforced by a JSON grammar, so it cannot skip them); the harness supplies the
    facts it can check itself (recent actions and how often each one already ran). Returns the messages for the action."""
    recent = [(c["function"]["name"], c["function"]["arguments"]) for m in msgs if m["role"] == "assistant"
              for c in m.get("tool_calls") or []][-6:]
    counts = {}
    for k, (n, _) in st.ran.items():
        counts[k] = n
    lines = []
    for name, arg in recent:
        n = sum(v for k, v in counts.items() if str(k).find(arg[:80].strip("{}")) >= 0) if arg else 0
        lines.append(f"- {name} {one_line(arg)[:160]}" + (f"  (already run {n} times)" if n > 1 else ""))
    typed = "slots_typed" in st.feats
    unified = "unified" in st.feats
    if unified and not st.todo:
        ask = ("[harness] Before your first action, fill in these fields:\n"
               "checklist: every requirement of the task, ONE complete requirement per item in under 25 words (exact file names, "
               "formats, edge cases, checks to run). Never split one sentence over two items.\n"
               "note: one short sentence on what you look for first.\n"
               "action: your first action (read a file or search).")
    elif unified:
        r = st.rec
        facts = ["Checklist:"] + [f"{'[x]' if i['status'] == 'done' else '[ ]'} {i['text']}" for i in st.todo]
        if r["test_step"] >= 0:
            facts.append(f"Last test run: {'passed' if r['test_ok'] else 'FAILED'}"
                         + (" (before your latest change)" if r["test_step"] < r["edit_step"] else ""))
        if r["test_step"] == r["step"] and r["test_ok"] and any(i["status"] != "done" for i in st.todo):
            facts.append("Your latest test PASSED. Set completed to the checklist item it verifies (if any).")
        facts += file_facts(st)
        still = r["step"] - r["edit_step"]
        if still >= 6:
            facts.append(f"No file has changed for {still} steps" + (" while a check still fails. Stop probing with variations; "
                         "read the source the failing check exercises, find the cause, edit it." if not r["test_ok"] else "."))
        ask = ("[harness] Before your next action, fill in these fields:\n"
               "finding: the most important thing you know now about the problem.\n"
               "completed: the checklist item your latest result showed is done and verified (or none).\n"
               "note: one short sentence with the specific detail (names, values, line) and why the action below is next.\n"
               "action: your next action. Only sensible actions are offered: files whose content is still shown above are not "
               "offered for reading, and finish is offered once the tests pass after your latest change.\n"
               + "\n".join(facts) + ("\nYour recent actions:\n" + "\n".join(lines) if lines else ""))
    elif typed:
        ask = ("[harness] Before your next action, fill in these fields:\n"
               "learned_new: did the latest tool result tell you something new?\n"
               "finding: the most important thing you know now about the problem.\n"
               "where: the file it is in (or none).\n"
               "repeating: would your next action repeat something already tried without a new reason?\n"
               "next / target: the kind of next action and the file it is about. If repeating is true, choose something else.\n"
               "note: one short sentence with the specific detail (names, values, line).\n"
               + ("Your recent actions:\n" + "\n".join(lines) if lines else ""))
    else:
      ask = ("[harness] Before your next action, fill in these fields (short, concrete):\n"
           "last_result: what the latest tool result showed and what it means for the task (do not copy it).\n"
           "still_missing: what the task still needs before it is complete (requirements, files, checks).\n"
           "tried_before: earlier actions or ideas that did not move you forward. Do not repeat them.\n"
           "next_action: ONE concrete next action that is different from those, and what result would show it worked. "
           "If everything is done and checked, say finish.\n"
           + ("Your recent actions:\n" + "\n".join(lines) if lines else ""))
    q = msgs + [{"role": "user", "content": ask}]
    r = base.chat(q, offered, max_tokens=900, temperature=temp,
                  extra={"response_format": {"type": "json_schema", "json_schema": {"name": "notes",
                         "schema": typed_schema(st.workdir, st, msgs) if typed else SLOT_SCHEMA}}})
    notes = r["message"].get("content") or ""
    for tries in range(3):
        try:
            d = json.loads(notes)
        except ValueError:
            break
        bad = check_notes(d, msgs, st) if "slots_check" in st.feats else []
        if not bad or tries == 2:
            if bad:
                st.notes_bad = bad
            st.notes_d = d
            if unified and "checklist" in d:
                st.todo = [{"text": str(t)[:160], "status": "pending"} for t in d["checklist"]][:12]
            elif unified and d.get("completed") not in (None, "none"):
                for i in st.todo:
                    if i["text"] == d["completed"]:
                        i["status"] = "done"
            notes = "\n".join(f"{k}: {v}" for k, v in d.items())
            break
        st.notes_rejects = getattr(st, "notes_rejects", 0) + 1
        q = q + [{"role": "assistant", "content": notes}, {"role": "user", "content":
                 "[harness] These notes do not match what actually happened:\n- " + "\n- ".join(bad) + "\nFill in the fields again."}]
        r = base.chat(q, offered, max_tokens=900, temperature=temp,
                      extra={"response_format": {"type": "json_schema", "json_schema": {"name": "notes", "schema": typed_schema(st.workdir, st, msgs)}}})
        notes = r["message"].get("content") or ""
    act = (getattr(st, "notes_d", None) or {}).get("action") if unified else None
    go = f"[harness] Now do exactly this with one tool call: {act}." if act else "[harness] Now do your next_action with one tool call."
    return notes, q + [{"role": "assistant", "content": notes}, {"role": "user", "content": go}]


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


def protect_inputs(st, task, log, chmod=True):
    """Before the agent starts: provided non-code files the task does not ask to change become read-only."""
    st.protected = set()
    for p in sorted(st.seed_bytes):
        # v8u (chmod=False) also asks about the provided tests: tasks often say "do not change tests/"
        if (p.endswith(".py") and (chmod or not p.startswith("tests/"))) or p.startswith(".agent/"):
            continue
        q = ("Task given to an AI agent:\n<task>\n" + task[:2500] + "\n</task>\n"
             f"The file `{p}` is provided with the task. Does the task ask the agent to change, overwrite or fix "
             f"the content of `{p}` itself (not just read it as input)? Answer modify=true only if so.")
        val, pr, ms = judge.ask(q, "modify")
        st.judge_log.append(("protect:" + p, val, round(pr, 3), ms))
        if val is False:
            full = os.path.join(st.workdir, p)
            try:
                # v8u: no chmod. Tests that copy an input (shutil.copy keeps the mode) then could not write the copy, so
                # the project's own tests failed before any change (cmd_registry). write_file/edit_file still refuse it.
                if chmod:
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


def isolated(st, box, cmd, timeout):
    """Run a check command and undo its side effects on the workspace: the agent's own spec test may write, delete
    or clean up files (v7e dedupe: its cleanup deleted the real output names_unique.txt during the finish check)."""
    skip = lambda p: p.startswith(".agent/") or "__pycache__" in p
    before = {}
    snap = {p: h for p, h in snapshot(st.workdir, before).items() if not skip(p)}
    r = box.sh(cmd, timeout=timeout)
    after = {p: h for p, h in snapshot(st.workdir).items() if not skip(p)}
    for p in set(snap) | set(after):
        full = os.path.join(st.workdir, p)
        if p not in snap:
            try:
                os.remove(full)
            except OSError:
                pass
        elif after.get(p) != snap[p] and p in before:
            mode = os.stat(full).st_mode if os.path.exists(full) else None
            try:
                os.makedirs(os.path.dirname(full), exist_ok=True)
                if mode is not None:
                    os.chmod(full, 0o644)
                with open(full, "wb") as f:
                    f.write(before[p])
                if mode is not None:
                    os.chmod(full, mode)
            except OSError:
                pass
    return r


def missing_numbers(task, report):
    """Numbers in the task text that appear nowhere in the report (the report already gives radius and diameter)."""
    nums = lambda t: [float(x) for x in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)", t)]
    have = set()
    for x in nums(report.replace("-", " ")):
        have.add(round(x, 2))
    out = []
    for x in nums(task.split("共通の約束")[0]):
        if x not in (0.0, 1.0) and round(x, 2) not in have and f"{x:g}" not in out:
            out.append(f"{x:g}")
    return out


def harness_checks(box, st=None):
    """Run what the harness can verify by itself: compile all .py files, run unittest/test files if present."""
    lines = []
    code, out, err = box.sh("python3 -m compileall -q . >/dev/null 2>/tmp/ce; c=$?; tail -c 600 /tmp/ce; exit $c", timeout=30)
    lines.append(f"compile all python files: exit {code}" + (f" ({(out + err).strip()[-300:]})" if code else ""))
    code, out, _ = box.sh("ls test_*.py tests/test_*.py 2>/dev/null | head -5")
    if out.strip():
        cmd = "python3 -m unittest discover -s tests -q 2>&1 | tail -3; for f in test_*.py; do [ -f \"$f\" ] && python3 \"$f\" 2>&1 | tail -2; done"
        c2, o2, e2 = isolated(st, box, cmd, 60) if st else box.sh(cmd, timeout=60)
        lines.append(f"tests found ({' '.join(out.split())}): output tail: {(o2 + e2).strip()[-400:]}")
    return "\n".join(lines)


def failing_tests(box, st=None):
    """Run the project's tests; return the failure report, or None when everything passes (or there are no tests)."""
    code, out, _ = box.sh("ls tests/test_*.py test_*.py 2>/dev/null | head -20")
    if not out.strip():
        return None
    reports = []
    if "tests/" in out:
        c, o, e = (isolated(st, box, "python3 -m unittest discover -s tests 2>&1 | tail -40", 120) if st
                   else box.sh("python3 -m unittest discover -s tests 2>&1 | tail -40", timeout=120))
        if "FAILED" in o or ("Error" in o and not o.rstrip().endswith("OK")):
            reports.append(o.strip()[-2500:])
    for f in [x for x in out.split() if "/" not in x]:
        c, o, e = (isolated(st, box, f"python3 -m unittest {f[:-3]} 2>&1 | tail -30", 120) if st
                   else box.sh(f"python3 -m unittest {f[:-3]} 2>&1 | tail -30", timeout=120))
        if "FAILED" in o:
            reports.append(o.strip()[-1500:])
    return "\n\n".join(reports) or None


def lint_unresolved(st):
    """LINT: findings of know.lint still present in the .py files the agent wrote or changed -> list of '- file: msg'"""
    try:
        import know
        left, now = [], snapshot(st.workdir)
        for dp, dns, fns in os.walk(st.workdir):
            dns[:] = [d for d in dns if not d.startswith(".") and d != "__pycache__"]
            for fn in fns:
                rel = os.path.relpath(os.path.join(dp, fn), st.workdir)
                if not fn.endswith(".py") or fn in ("vbcompat.py", "pwkit.py", "sqlkit.py") or (rel in st.seed and st.seed.get(rel) == now.get(rel)):
                    continue
                text = open(os.path.join(dp, fn), encoding="utf-8", errors="replace").read()
                left += [f"- {rel}: {m}" for _, m in know.lint(st.know_keys, rel, text, root=st.workdir)]
        return left
    except Exception as e:
        if st.log:
            st.log({"lint_unresolved_error": repr(e)[:200]})
        return []


def on_finish(box, st, task, messages, args, in_context=False, cf=False, tools=None):
    if os.environ.get("LINT") == "1" and getattr(st, "know_keys", None) and not st.__dict__.get("lint_finish_done"):
        # cycle 49 h_vba_kintai: the tx-crcr finding was shown once and ignored; the final code still wrote \r\r\n.
        # At the first finish, every finding still present in the code goes back once.
        st.lint_finish_done = True
        left = lint_unresolved(st)
        if left:
            if st.log:
                st.log({"lint_finish": len(left)})
            return ("[harness] Not accepted yet: these problems are still in your code (each was reported when you wrote "
                    "the file). Fix each one, or if a finding does not apply, say why in one line; then call finish again.\n"
                    + "\n".join(left[:8]))
    if st.hard_tests and st.test_gate_tries < 4:
        rep = failing_tests(box, st)
        if rep:
            st.test_gate_tries += 1
            return ("[harness] Not accepted: the project's tests fail. Fix the code (do not edit existing tests unless the task "
                    "asks), re-run them, then call finish.\n" + rep)
    st.finish_tries += 1
    if st.finish_tries > 2:
        if {"unified", "fixes"} & set(getattr(st, "feats", ())) and st.spec:
            # v8u price_cache: the 3rd finish was accepted although its own reproduction test still failed to import,
            # so the second bug was never checked; the spec test stays a hard gate (the step cap still ends the run)
            code, out, err = isolated(st, box, "test -f .agent/spec_test.py || exit 0; PYTHONPATH=. python3 .agent/spec_test.py", 60)
            if code != 0:
                return ("[harness] Not accepted: .agent/spec_test.py still fails:\n" + base.clip((out + err).strip(), 1200)
                        + "\nMake it run and pass (fix the test if the test itself is wrong), then call finish.")
        return audit(st, task, args)
    open_items = [i["text"] for i in st.todo if i["status"] not in ("done", "dropped")]
    checks = harness_checks(box, st)
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
    if st.cad:
        # the part must build into one valid solid before anything else is judged
        code, out, err = box.sh("test -f model.py || exit 99; python3 /opt/cad/cadtool.py model.py", timeout=120)
        rep = (out + err).strip()
        try:  # the final report is published with the part (deploy/agent_server.py)
            os.makedirs(os.path.join(st.workdir, ".agent"), exist_ok=True)
            open(os.path.join(st.workdir, ".agent", "cad_report.txt"), "w").write(rep)
        except OSError:
            pass
        if code == 99:
            return "[harness] Not accepted: model.py does not exist. Write the part in model.py (result = ...) and build it with cadtool."
        assembly = "\nparts:" in rep   # PARTS: several coloured parts, each may hold several solids (v8c airliner)
        if code != 0 or "valid: True" not in rep or (not assembly and "solids: 1 " not in rep):
            need = "every part must build into valid solids" if assembly else "the part must build into exactly one valid solid"
            return (f"[harness] Not accepted: {need}. cadtool says:\n" + base.clip(rep, 1500)
                    + "\nFix model.py, run cadtool again, compare every dimension of the task with the report, then call finish.")
        if not st.cad_numbers_checked:
            # every dimension in the task should show up somewhere in the measured report (v8c cad_cbore used
            # cskHole for a counterbore and finished without noticing that no 11 mm diameter existed)
            st.cad_numbers_checked = True
            missing = missing_numbers(task, rep)
            if missing:
                return ("[harness] Not accepted yet: these numbers from the task do not appear in the cadtool report: "
                        + ", ".join(missing) + ". For each one, find the feature it belongs to in the report (a diameter, "
                        "length, position or size). If it is missing or different, fix model.py and run cadtool again. If a number "
                        "is a count, an angle cadtool already shows another way, or something cadtool cannot measure (for example "
                        "a chamfer on a straight edge), check it yourself. Then call finish again.\ncadtool report:\n" + rep[:1500])
        png = os.path.join(st.workdir, "model.png")
        if not st.cad_image_shown and os.path.exists(png):
            # the model checks numbers but rarely looks (v8c airliner: fuselage built vertical, never viewed)
            st.cad_image_shown = True
            st.pending_image = png
            return ("[harness] Not accepted yet: look at the four views of your model in the next message. For every "
                    "component the task asks for, say in a think call whether it is there, in the right place and pointing "
                    "the right way (for example a fuselage along X, wheels outside the body, windows visible). Fix anything "
                    "that is wrong, run cadtool again, then call finish.")
        checks += "\ncadtool report:\n" + rep[:1500]
    webart = "webart" in (getattr(st, "know_keys", None) or [])
    if webart and os.path.isdir(os.path.join(st.workdir, ".agent", "webkit")):
        # voxel / 3D page: the render report is the test (a spec_test.py of asserts says nothing about a picture)
        code, out, err = box.sh("test -f index.html || exit 99; python3 .agent/webkit/render.py index.html .agent/shot.png", timeout=90)
        rep = (out + err).strip()
        if code == 99:
            return "[harness] Not accepted: index.html does not exist. Build it: python3 .agent/webkit/build.py scene.js index.html"
        if code != 0:
            return ("[harness] Not accepted: the page does not render cleanly. render.py says:\n" + base.clip(rep, 1500)
                    + "\nFix scene.js, build and render again, then call finish.")
        m_parts = re.search(r"^parts: (\d+) labelled kinds", rep, re.M)
        m_vox = re.search(r"^voxelkit: (\d+) voxels.*?\"island\": (\d+)", rep, re.M)
        thin = (m_parts and int(m_parts.group(1)) < 6) or (m_vox and int(m_vox.group(1)) - int(m_vox.group(2)) < 1500)
        if st.__dict__.get("webart_review") and thin and st.__dict__.get("webart_thin", 0) < 2:
            # cycle 55: two runs cut scene.js down to 3-6 lines to get rid of an error and finished with an empty island
            st.webart_thin = st.__dict__.get("webart_thin", 0) + 1
            return ("[harness] Not accepted: the scene is too thin for the task (few labelled parts / few voxels besides the "
                    "island). Do not shrink the scene to get rid of an error - fix the reported line instead. Build the "
                    "hero and 8+ labelled supporting parts again, then build, render and call finish.\n" + base.clip(rep, 800))
        shot = os.path.join(st.workdir, ".agent", "shot.png")
        if VISION and os.path.exists(shot) and st.__dict__.get("webart_fid", 0) < 2:
            # prompt fidelity on the picture: the things the task names must be recognizable at a glance
            # (cycle 62: "castle" runs made grey pagodas, "lighthouse" runs had no harbor or boats - all scored 12/12)
            try:
                sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "webkit"))
                import fidelity
                fidelity.API = os.environ.get("JUDGE_API") or os.environ.get("AGENT_API", fidelity.API)
                if not st.__dict__.get("webart_things"):
                    st.webart_things = fidelity.things(st.task)
                res = [(t, *fidelity.present(shot, t)) for t in st.webart_things]
                miss = [t for t, v, p in res if p < 0.5]
                if st.log:
                    st.log({"fidelity": [(t, round(p, 2)) for t, v, p in res]})
                if miss:
                    st.webart_fid = st.__dict__.get("webart_fid", 0) + 1
                    st.pending_image = shot
                    # cycle 66: VK.harbor existed but no run used it - name the tested function for each missing thing
                    hints = {"harbor": "VK.harbor(x, z) at a shore point on the camera side (+x, +z), after VK.sea", "harbour": "VK.harbor(x, z)", "port": "VK.harbor(x, z)",
                             "boat": "VK.boat(x, z) on the sea or VK.harbor", "ship": "VK.boat(x, z, {len: 9})",
                             "castle": "VK.wall x4 + VK.tower({roof: 'cone'}) corners + VK.building({roof: 'battlement'}) keep",
                             "town": "VK.town(x, z, {houses: 10})", "village": "VK.town(x, z, {houses: 8})", "market": "VK.town (has market stalls)",
                             "lighthouse": "VK.tower({roof: 'lantern', stripes: [0xf3ede1, 0xc0392b], h: 18})",
                             "forest": "decorate({flora: 'conifer'}) or many VK.conifer", "pine": "VK.conifer", "snow": "VK.island({snow: true}) + VK.start({snow: true})",
                             "cabin": "VK.house (keep trees 4+ voxels away so it is visible)", "pagoda": "VK.building({storeys: 5, taper: 0.75})",
                             "cape": "a hill at the island edge (VK.island hill) with rocks", "mountain": "VK.island({hill: [x, z, 18, 14]}) - a big hill",
                             "garden": "VK.decorate + VK.pond + VK.path + VK.lantern"}
                    tips = [f"{t}: {next(v for k, v in hints.items() if k in t.lower())}" for t in miss if any(k in t.lower() for k in hints)]
                    return ("[harness] Not accepted yet: looking at the screenshot (next message), these things the task asks for "
                            "are NOT recognizable at a glance: " + ", ".join(miss) + ". Make each one clearly what it is and big "
                            "enough to see from the default camera (right shape, typical details and colors, placed where it is "
                            "visible), then build, render and call finish again."
                            + ("\nTested kit functions for them:\n" + "\n".join("- " + t for t in tips) if tips else ""))
            except Exception as e:
                if st.log:
                    st.log({"fidelity_error": repr(e)[:200]})
        if not st.__dict__.get("webart_review"):
            if VISION and os.path.exists(os.path.join(st.workdir, ".agent", "shot.png")):
                st.pending_image = os.path.join(st.workdir, ".agent", "shot.png")
                rep = "(the screenshot is shown in the next message - judge the PICTURE first)\n" + rep
            # cycle 53: the first kit scene was clean but thin (3 trees, the pagoda standing in the pond, 100 lines)
            st.webart_review = True
            return ("[harness] Not accepted yet - the page renders; now make it rich. render.py says:\n" + base.clip(rep, 1200)
                    + "\nIn a think call, check each point and then improve scene.js:\n"
                    "1. The hero structure: is it big (it should dominate the picture) and detailed (several tiers/levels, "
                    "pillars, trims, ornaments, a top piece), and does it stand on solid ground (not in water)? Between stacked roofs "
                    "the walls, pillars and windows must stay visible: each storey needs a body taller than its roof layers.\n"
                    "2. Count the supporting element kinds (labels above): a rich scene has 8 or more (water, bridge, gate, "
                    "lanterns, path, 2-3 tree kinds, shrubs, flowers, rocks, fence...). Add the missing ones, placed so they "
                    "do not overlap each other.\n3. Life: petals / animals / lights that move.\n"
                    "4. Nothing floating and nothing standing in water (see 'floating' / 'over the pond' above).\n"
                    "Then build and render again, and call finish.")
        checks += "\nrender report:\n" + rep[:1200]
    if st.spec and not webart:
        code, out, err = isolated(st, box, "test -f .agent/spec_test.py || exit 99; PYTHONPATH=. python3 .agent/spec_test.py", 60)
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
    return audit(st, task, args)


T_FAILURES = {"type": "function", "function": {"name": "verdict", "description": "Give your verdict. This ends the review.",
              "parameters": {"type": "object", "properties": {
                  "failures": {"type": "array", "description": "only requirements you SHOWED to fail by running something; empty if none",
                               "items": {"type": "object", "properties": {
                                   "requirement": {"type": "string", "description": "the requirement, quoting the task"},
                                   "evidence": {"type": "string", "description": "the exact command you ran, the output you got and what the task expects instead"}},
                                   "required": ["requirement", "evidence"]}}},
                  "required": ["failures"]}}}


REQ_PROMPT = ("List every concrete, checkable requirement in the text below: outputs and their exact format (line ends, "
              "encoding, separators, number formats), commands that must work, files that must not change, and every "
              "rule the result depends on, including edge cases (invalid input, boundaries, ties, empty input, rounding, "
              "errors, re-running). One atomic rule per item (one fact each, not several joined), quoting exact values.")


# manuals the harness itself puts next to a task: their examples are not requirements (q_cad_ramp_bracket: the sample
# `assert len(holes) == 4` in CADTOOL.md became "the number of holes must be 4", and a fast judgment could not tell)
HARNESS_DOCS = {"docs/CADTOOL.md"}


def extract_reqs(st, task):
    """from the task and from each doc separately, then merged: one call over everything dropped rules at random
    (q25 browser_export: 'line ends are LF' was in one extraction and missing from the next)"""
    import agent_g as G
    def chunks(text, n=600):
        """by paragraphs, about n characters each (dense Japanese specs: ~600): one call returns at most 20 items, so a long spec lost its later
        sections (q25 browser_export: the output-format section with 'line ends are LF')"""
        out, cur = [], ""
        for para in re.split(r"\n(?=#)|\n\s*\n", text):
            if cur and len(cur) + len(para) > n:
                out.append(cur); cur = ""
            cur += para + "\n\n"
        return out + ([cur] if cur.strip() else [])
    srcs = [("task", task)] + [(f"{rel} (part {i + 1})", c) for rel in G.files_of(st.workdir)
                               if rel.lower().endswith((".md", ".txt", ".rst")) and rel.lower() != "license"
                               and not rel.startswith(("data/", "out/", "tests/")) and rel not in HARNESS_DOCS
                               for i, c in enumerate(chunks(G.read(st.workdir, rel, 12000)))][:12]
    schema = {"type": "object", "properties": {"requirements": {"type": "array", "items": {"type": "string", "maxLength": 250}, "maxItems": 20}},
              "required": ["requirements"]}
    def one(src):
        name, text = src
        ctx = "" if name == "task" else f"(This is {name}, a document of the project. The task is:\n<task>\n{task[:3000]}\n</task>\nList only rules from {name} that the task relies on.)\n"
        return G.structured_safe(lambda: G.structured(ctx + REQ_PROMPT + f"\n\n<text>\n{text}\n</text>", schema, system=G.SYS)) or {}
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(one, srcs))
    out, seen = [], set()
    for d in res:
        for r in d.get("requirements", []):
            k = re.sub(r"\W+", " ", r.lower()).strip()
            if r.strip() and k not in seen:
                seen.add(k); out.append(r.strip())
    return out[:60]


def reqs_reminder(st):
    """v7r: once, at the first finish that every gate accepted"""
    if "reqs" not in st.feats or not st.reqs or st.audits:
        return None
    st.audits = 1
    return ("[harness] Not accepted yet: go through the checklist below once. For every item you have not yet checked by "
            "running something, check it now (run the program or page on the real inputs and look at the exact output). "
            "Fix what is wrong, then call finish.\n" + "\n".join(f"R{i + 1}. {r}" for i, r in enumerate(st.reqs)))


EV_Q = ("Task given to an engineer:\n<task>\n{task}\n</task>\n\nOne requirement of the task:\n{req}\n\n"
        "Facts about the engineer's finished result, collected automatically by running it (not written by the engineer):\n"
        "<facts>\n{facts}\n</facts>\n\nDo these facts clearly show that the result violates this requirement? Answer "
        "violated=false if the facts show it is met, or if they say nothing about this requirement.")
EV_M = ("Task given to an engineer:\n<task>\n{task}\n</task>\n\nOne requirement of the task:\n{req}\n\n"
        "Facts about the engineer's finished result, collected automatically by running it:\n<facts>\n{facts}\n</facts>\n\n"
        "Are these facts consistent with the requirement being met? Answer consistent=false only if a fact shown above "
        "directly contradicts the requirement.")
EV_D = ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n"
        "<facts>\n{facts}\n</facts>\n\nCan a reader decide whether this requirement is met just by reading these facts, "
        "with no calculation of their own, no guessing about inputs not shown, and no knowledge of the code? "
        "Answer decidable=true only if so.")


EV_DIRECT = ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n<facts>\n{facts}\n</facts>\n\n"
             "Is there a fact above that by itself shows, without any calculation, sorting, counting or reasoning about code, "
             "whether this requirement is met (for example a stated line-end count, an exact output line, an error message, "
             "or a 'DIFFERENT'/'identical' comparison)? Answer direct=true only if so.")


def cover_gate(st, log):
    """EV_COVER=1: no violation was found, so ask Jev per requirement whether the agent's own tests exercise it at all.
    10-24 cycles 22-24: 7 of 10 schema-3 failures were finishes the gate accepted (toposort: 5 own tests passed, the
    hidden check passed 29 of 54 cases: comments, repeated rules) -- an untested rule leaves no fact to be violated.
    "Is there a test case for X" is a narrower question than "is X met" (v7z's 26B-written checks flagged half of the
    correct results)."""
    import agent_g as G
    t0 = time.time()
    tests = []
    for rel in G.files_of(st.workdir):
        name = os.path.basename(rel)
        if rel.endswith(".py") and (rel.startswith(("tests/", ".agent/")) or name.startswith("test_") or "_test" in name):
            tests.append(f"=== {rel} ===\n{G.read(st.workdir, rel, 8000)}")
    code = "\n\n".join(tests)[:16000]
    if not code or not st.reqs:
        return None
    def ask(r):
        return G.judge(f"Test code of a project:\n<tests>\n{code}\n</tests>\n\nRequirement:\n{r}\n\nDoes this test code contain "
                       "a test case that exercises this requirement: an input that contains this situation, and a check of "
                       "the result for it?", key="covered")
    with ThreadPoolExecutor(6) as ex:
        ps = list(ex.map(ask, st.reqs))
    miss = [r for r, p in zip(st.reqs, ps) if p < 0.3]
    log({"cover_gate": st.audits, "seconds": round(time.time() - t0, 1), "missing": miss, "p": [round(p, 2) for p in ps]})
    if not miss:
        return None
    return ("[harness] Not accepted yet. Your tests do not exercise these requirements:\n" + "\n".join("- " + r for r in miss[:8])
            + "\nAdd one test case for each (an input with that situation, and the expected result taken from the task or docs), "
            "run the tests, fix what fails, then call finish.")


def evgate(st, task):
    """v7q: facts from the harness, judgments from Jev; a requirement goes back only when it is decidable from the
    facts, judged violated (p>=0.9) and judged inconsistent with being met (p<0.5), and the facts decide it (decidable
    or a direct fact). Tuned on 82 finished q25 results with known hidden-check verdicts (jev_replay.py)."""
    if st.audits >= 2:
        return None
    log = st.log or (lambda d: None)
    if getattr(st, "deadline", None) and time.time() > st.deadline:
        # cycle 33 sec_firewall: a finish after the deadline spent 9+ minutes in this gate and the job was killed
        # with no result; past the deadline the hidden check decides
        log({"evgate_skipped": "past deadline"})
        return None
    st.audits += 1
    import agent_g as G, evidence
    t0 = time.time()
    log({"evgate_start": st.audits})
    try:
        pre = st.__dict__.get("midgate", {}).get("reqs")
        if st.reqs is None and pre is not None and pre.is_alive():
            pre.join(timeout=240)   # MIDGATE is already extracting them
        if st.reqs is None:
            st.reqs = extract_reqs(st, task)
            log({"reqs": st.reqs})
        start_probes(st, task, log)   # no-op unless EV_PROBES=1; normally started by MIDGATE at the first step
        facts = evidence.collect(st.workdir, st.seed_dir, task, probes=get_probes(st))
        log({"evgate_facts_s": round(time.time() - t0, 1)})
        bad, scores = evidence.judge_reqs(task, st.reqs, facts, evidence.docs_text(st.seed_dir or st.workdir))
        # EV_DOCEX: a worked example from the docs that the result does not reproduce is a fact, not a judgment: the
        # finish goes back without asking Jev (the harness owns the finish)
        bad = bad + [l.split(": DIFFERS", 1)[0] + " does not reproduce the docs: " + l.split("DIFFERS from the docs: ", 1)[1][:300]
                     for l in facts.splitlines() if l.startswith("Docs example") and "): DIFFERS from the docs: " in l]
        log({"evgate": st.audits, "seconds": round(time.time() - t0, 1), "bad": bad, "cand": scores["cand"]})
    except Exception as e:
        log({"audit_error": repr(e)[:400]})
        return None
    if not bad and os.environ.get("EV_COVER") == "1":
        return cover_gate(st, log)
    if not bad:
        return None
    return ("[harness] Not accepted yet. The harness ran your result and collected these facts:\n<facts>\n" + facts[:5000]
            + "\n</facts>\nAccording to these facts, these requirements are not met:\n" + "\n".join("- " + r for r in bad)
            + "\nCheck each one yourself. Fix the cause, or if a finding is wrong (the facts do not really show it), say why "
            "in your next message. Then call finish.")


def start_probes(st, task, log):
    """EV_PROBES=1: probe commands written once from the docs, in the background from the first step"""
    import threading
    if os.environ.get("EV_PROBES") != "1" or "probes_thread" in st.__dict__ or not st.seed_dir:
        return

    def work():
        import evidence
        try:
            st.probes = evidence.make_probes(st.seed_dir, task)
            log({"probes": st.probes})
        except Exception as e:
            st.probes = []
            log({"probes_error": repr(e)[:300]})
    st.probes = None
    st.probes_thread = threading.Thread(target=work, daemon=True)
    st.probes_thread.start()


def get_probes(st, wait=180):
    t = st.__dict__.get("probes_thread")
    if t is None:
        return None
    t.join(timeout=wait)
    return st.__dict__.get("probes") or None


def midgate_tick(st, task, workdir, messages, log):
    """MIDGATE=1: the finish gate's facts + Jev judgment, run in a background thread at fractions of the deadline
    (MIDGATE_AT, default 0.35/0.65; "/" because cycle.py splits variant env on ",") while the model keeps working; violated requirements are handed over at the next
    step, nothing is said when none is found. Replay 10-24 (scores-sweep, 860 results): the gate flagged 181 of 290
    results that ran out of time unsolved and 0 of 354 solved ones, but a timed-out run never reaches the finish gate
    (142 of 321 v7o runs timed out). midfacts (facts at steps 30/55, no judgment) came at ~480 s or never."""
    import threading
    mg = st.__dict__.setdefault("midgate", {"done": 0, "thread": None, "result": None, "snap": None, "reqs": None})
    if mg["reqs"] is None and st.reqs is None:
        # requirements are extracted once, in the background from the first step (smoke 10-24: extracting them inside
        # the first midgate under cycle load took >3 min, so its findings would have come at ~370 s of 540)
        def pre():
            try:
                r = extract_reqs(st, task)
                if not r:   # cycle 41 cad_wheel: [] under load, and MIDGATE then had nothing to judge
                    r = extract_reqs(st, task)
                if st.reqs is None:
                    st.reqs = r
                    log({"reqs": r})
            except Exception as e:
                log({"midgate_error": "reqs: " + repr(e)[:300]})
        mg["reqs"] = threading.Thread(target=pre, daemon=True)
        mg["reqs"].start()
    start_probes(st, task, log)
    if mg["result"] is not None:
        bad, facts, t = mg["result"]
        mg["result"] = None
        log({"midgate_result": mg["done"], "bad": bad, "seconds": t})
        left = lint_unresolved(st) if os.environ.get("LINT") == "1" and getattr(st, "know_keys", None) else []
        if left:
            # cycle 50: a run that never calls finish never saw its ignored findings again
            messages.append({"role": "user", "content": "[harness] These problems found when you wrote your files are still "
                             "in the code - fix them now:\n" + "\n".join(left[:8])})
            log({"midgate_lint": len(left)})
        if bad:
            messages.append({"role": "user", "content": "[harness] While you worked, the harness ran your current files "
                             "on a fresh copy and collected these facts:\n<facts>\n" + facts[:5000] + "\n</facts>\n"
                             "According to these facts, these requirements of the task are NOT met yet:\n"
                             + "\n".join("- " + r for r in bad) + "\nCheck each against the facts; fix the cause in the "
                             "code (your own test may agree with the wrong behaviour - the facts come from running the "
                             "task's commands, not your test). If a finding is wrong, say why, then go on."})
            st.hot = 1
        return
    if mg["thread"] is not None and mg["thread"].is_alive():
        return
    ats = [float(x) for x in os.environ.get("MIDGATE_AT", "0.35/0.65").replace(",", "/").split("/")]
    total = float(os.environ.get("TASK_DEADLINE", "540"))
    elapsed = total - (st.deadline - time.time())
    if mg["done"] >= len(ats) or elapsed < ats[mg["done"]] * total or st.deadline - time.time() < 60:
        return
    snap = snapshot(workdir)
    if snap == mg["snap"]:
        return   # nothing changed since the last midgate: same facts, same answer
    mg["snap"] = snap
    mg["done"] += 1
    log({"midgate_start": mg["done"], "elapsed": round(elapsed)})

    def work():
        import evidence
        t0 = time.time()
        try:
            # cycle 40 html_form: with probes and the Chromium look the facts took 343 s and came at the deadline
            facts = evidence.collect(workdir, st.seed_dir, task, probes=get_probes(st, wait=60),
                                     budget=float(os.environ.get("MIDGATE_BUDGET", "90")))
            if mg["reqs"] is not None:
                mg["reqs"].join(timeout=240)
            if not st.reqs:
                log({"midgate_error": "no requirements yet"})
                return
            bad, scores = evidence.judge_reqs(task, st.reqs, facts, evidence.docs_text(st.seed_dir or workdir))
            mg["result"] = (bad, facts, round(time.time() - t0, 1))
        except Exception as e:
            log({"midgate_error": repr(e)[:300]})
    mg["thread"] = threading.Thread(target=work, daemon=True)
    mg["thread"].start()


def audit(st, task, args):
    """v7z: the main loop says it is done and every gate agreed. A reviewer with a fresh context checks each requirement
    on a disposable copy by running the real program (q25 10-23: 10 of 14 v7x failures were finishes that missed one or
    two spec rules: CRLF line ends, invalid quantity -> 0, a named group, an existing table). Reported failures are
    confirmed one by one with a fast boolean judgment, then sent back as concrete findings (at most twice)."""
    if "reqs" in st.feats:
        return reqs_reminder(st)
    if "evgate" in st.feats:
        return evgate(st, task)
    if "audit" not in st.feats or st.audits >= 2:
        return None
    st.audits += 1
    import agent_g as G
    log = st.log or (lambda d: None)
    t0 = time.time()
    try:
        if st.reqs is None:
            docs = "\n\n".join(f"=== {rel} ===\n{G.read(st.workdir, rel, 4000)}" for rel in G.files_of(st.workdir)
                                if rel.lower().endswith((".md", ".txt", ".rst")) and rel.lower() != "license")[:12000]
            req = G.structured(
                f"Task:\n<task>\n{task}\n</task>\n\nDocs:\n{docs}\n\n"
                "List every concrete, checkable requirement of the task: outputs and their exact format (line ends, "
                "encoding, separators, number formats), commands that must work, files that must not change, and every "
                "rule in the task or docs the result depends on, including edge cases (invalid input, boundaries, ties, "
                "empty input, rounding, errors, re-running). One atomic rule per item, quoting exact values.",
                {"type": "object", "properties": {"requirements": {"type": "array", "items": {"type": "string", "maxLength": 300}, "maxItems": 24}},
                 "required": ["requirements"]}, system=G.SYS)
            st.reqs = [r for r in req.get("requirements", []) if r.strip()][:24]
        log({"audit_reqs": st.reqs})
        ws = G.copy_ws(st.workdir, os.path.join(os.path.dirname(st.workdir), f"audit{st.audits}"))
        image = base.sandbox_for(st.workdir)[0] or ""
        env_note = G.WEB_NOTE if "web" in image else G.CAD_NOTE if "cad" in image else ""
        changed = [rel for rel in G.files_of(ws) if rel.endswith(G.CODE_EXT) and os.path.getsize(os.path.join(ws, rel)) < 60000
                   and st.seed.get(rel) != snapshot(ws).get(rel)]
        srcs = "\n\n".join(f"=== {rel} ===\n{G.read(ws, rel, 6000)}" for rel in changed)[:16000]
        head = (f"Task given to an engineer:\n<task>\n{task[:6000]}\n</task>\n\nProject files:\n{G.outline(ws)}\n"
                f"Files the engineer wrote or changed:\n{srcs}\n" + env_note + "\n\n")
        # 1. one check command per requirement, written independently (the agent-style auditor spent its turns
        #    re-grepping one line and never checked the line ends the spec asked for)
        def plan(r):
            return G.structured(head + f"Requirement to verify:\n{r}\n\nWrite ONE bash command (it may run a short python3 -c "
                                "or heredoc script) that checks this requirement on the engineer's real result: run the program, "
                                "page or command the task names (start servers it needs in the background and stop them), on the "
                                "real inputs, and print the facts that decide it (for formats print repr() of the exact bytes or "
                                "lines). Write scratch files only under /tmp. Everything needed is installed and there is no network: never install "
                                "anything. Keep it short and fast (under 40 s). Prefer a heredoc python3 script over a one-line "
                                "python3 -c with if/for (that is a syntax error). Also say what output a correct result gives.",
                                {"type": "object", "properties": {"command": {"type": "string", "maxLength": 3000},
                                 "expect": {"type": "string", "maxLength": 400}}, "required": ["command", "expect"]}, system=G.SYS)
        with ThreadPoolExecutor(6) as ex:
            plans = list(ex.map(lambda r: G.structured_safe(plan, r), st.reqs))
        # 2. the harness runs every check on a fresh copy of the result
        box = base.Sandbox(ws)
        fresh = "rm -rf /tmp/w && cp -a /work /tmp/w && cd /tmp/w && export PYTHONPATH=/tmp/w && "
        runs = []
        try:
            for r, pl in zip(st.reqs, plans):
                if not pl or not pl.get("command"):
                    continue
                code, out, err = box.sh(fresh + "{\n" + pl["command"] + "\n}", timeout=60)
                runs.append((r, pl, code, base.clip(f"exit code: {code}\n{out}\n{err}".strip(), 2000)))
        finally:
            box.close()
        def broken(out):
            """the check itself failed: its own syntax error or traceback, a timeout, a missing tool or file"""
            if "exceeded 60 s" in out or "command not found" in out or "No module named" in out:
                return True
            tb = re.findall(r'File "([^"]+)", line', out)
            return bool(tb) and all(f.startswith(("<string>", "<stdin>", "/tmp/")) and not f.startswith("/tmp/w/") for f in tb)
        bad = [x for x in runs if broken(x[3])]
        runs = [x for x in runs if not broken(x[3])]
        # 3. a fast boolean judgment per check: does the output show a real violation?
        def weigh(x):
            r, pl, code, out = x
            return G.judge("Task:\n<task>\n" + task[:4000] + f"\n</task>\nRequirement: {r}\nCheck command:\n{pl['command'][:1500]}\n"
                           f"A correct result gives: {pl.get('expect', '')}\nActual output:\n{out}\n\nDoes this output show that the "
                           "engineer's result violates the requirement? Answer violated=false if it is correct, or if the output only "
                           "shows a mistake in the check command itself (syntax error, wrong file name, wrong way of starting it).", "violated")
        with ThreadPoolExecutor(6) as ex:
            ps = list(ex.map(weigh, runs))
        kept = [{"requirement": r, "evidence": f"$ {pl['command'][:600]}\n{out[:700]}\nexpected: {pl.get('expect', '')}", "p": round(p, 3)}
                for (r, pl, code, out), p in zip(runs, ps) if p >= 0.7]
        kept = sorted(kept, key=lambda f: -f["p"])[:6]
        log({"audit": st.audits, "checks": len(runs), "broken": len(bad), "kept": len(kept), "seconds": round(time.time() - t0, 1),
             "all": [(r[:80], round(p, 2)) for (r, *_), p in zip(runs, ps)], "failures": kept})
    except Exception as e:
        log({"audit_error": repr(e)[:400]})
        return None
    if not kept:
        return None
    return ("[harness] Not accepted yet: an independent reviewer checked your result and found these problems:\n"
            + "\n".join(f"- {f.get('requirement', '')}\n  evidence: {str(f['evidence'])[:700]}" for f in kept)
            + "\nReproduce each one. Fix the cause, or if a finding is wrong because the check misread the task, say why in "
            "your next message. Re-run your checks and the tests, then call finish.")


def run_task(task_text, workdir, profile, log):
    if "cad" in feats(profile):  # CadQuery image with the measuring/drawing tool mounted at /opt/cad
        box = base.make_sandbox(workdir, CAD_IMAGE, [f"{os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cad')}:/opt/cad:ro,Z"])
    else:
        box = base.make_sandbox(workdir)
    st = State()
    st.v6b = "v6b" in feats(profile)
    st.spec = "spec" in feats(profile)
    st.think_limit = "think_limit" in feats(profile)
    st.workdir = workdir
    st.log = log
    if "evgate" in feats(profile):  # the files as given, for "what changed" in the evidence
        st.seed_dir = os.path.join(os.path.dirname(workdir), "seed")
        shutil.rmtree(st.seed_dir, ignore_errors=True)
        shutil.copytree(workdir, st.seed_dir, symlinks=True)
    st.seed = snapshot(workdir, st.seed_bytes)
    st.restore = "restore_inputs" in feats(profile)
    st.hard_tests = "hard_tests" in feats(profile)
    st.read_window = "read_window" in feats(profile)
    st.cad = "cad" in feats(profile)
    if "protect_inputs" in feats(profile):
        protect_inputs(st, task_text, log, chmod=not {"unified", "fixes"} & feats(profile))
    st.judge_inputs = "judge_inputs" in feats(profile)
    if "keep_orig" in feats(profile):
        keep_originals(st, log)
        task_text += ("\n\n[harness] Read-only copies of the files as they were given are in .agent/orig/ "
                      "(for example .agent/orig/" + (sorted(st.seed_bytes) or ["file"])[0] + "). Use them whenever you need the original code or data again.")
    t0 = time.time()
    F = feats(profile)
    st.feats = F
    if "reqs" in F:
        try:
            st.reqs = extract_reqs(st, task_text)
            log({"reqs": st.reqs})
        except Exception as e:
            log({"reqs_error": repr(e)[:300]})
        if st.reqs:
            task_text += ("\n\n[harness] Checklist of the task's requirements (extracted automatically; the task text above "
                          "wins if they disagree). Keep every item in mind and check each one on the real output before "
                          "calling finish:\n" + "\n".join(f"R{i + 1}. {r}" for i, r in enumerate(st.reqs)))
    st.task = task_text
    think = "think" in F
    tools = TOOLS + [THINK_TOOL] if think else TOOLS
    if "unified" in F:
        tools = [t for t in tools if t["function"]["name"] != "todo"]
    if "cad" in F or (VISION and re.search(r"voxel|three\.js|webgl|\b3d\b|ボクセル|self-contained html", task_text, re.I)):
        tools = tools + [VIEW_IMAGE_TOOL]
    sys0 = SYSTEM
    if "unified" in F:  # no todo tool: the checklist lives in the notes the harness asks for before every action
        sys0 = (SYSTEM.replace("1. First call todo with a short checklist of the task's requirements (exact file names, formats, edge cases).",
                               "1. Before every action the harness asks you for short notes; the first notes include a checklist of the "
                               "task's requirements (exact file names, formats, edge cases).")
                .replace("Mark todo items done only after verifying.", "Mark checklist items completed only after verifying.")
                .replace("When all todo items are done", "When all checklist items are done"))
    messages = [{"role": "system", "content": sys0 + (SYSTEM_THINK_RULE + (SYSTEM_THINK_SHORT if "think_limit" in F else "") if think else "") + (SYSTEM_V6B_RULES if "v6b" in F else "") + (SYSTEM_V6C_RULES if "spec" in F else "") + (SYSTEM_V7B_RULES if "v7b_rules" in F else "") + (SYSTEM_DEBUG_RULES if "debug_rules" in F else "") + (SYSTEM_CAD_RULES if "cad" in F else "") + (__import__("playbook").text("v7e") if "playbook" in F else "")},
                {"role": "user", "content": task_text}]
    if os.environ.get("KNOW") == "1":
        # KNOW: the documents/code in full + domain pitfall sheets at the start (know.py; 10-24 Claude-vs-Gemma on the
        # 6 tasks Gemma never passes: every Gemma failure there was a missing domain fact, not a missing step)
        try:
            import know
            keys, kmsg = know.message(workdir, task_text)
            st.know_keys = keys
            if "vba" in keys and os.environ.get("VBC") == "1":
                # VBC: a tested VBA runtime emulation (vbcompat.py) in the project, so the model calls CLng / Format /
                # DateSerial / ... instead of re-deriving them in code comments (cycle 46: vba_dates 6 comment stops per
                # run); a 52-line port of q_vba_sales on it passes the hidden check
                shutil.copy(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vbcompat.py"), os.path.join(workdir, "vbcompat.py"))
                kmsg += ("\n\n[harness] vbcompat.py is in the project: a TESTED module that reproduces the VBA runtime. Use it "
                         "(`from vbcompat import *`) instead of writing these functions yourself - every function behaves exactly "
                         "like the VBA one, including the cases where VBA differs from Python. Keep vbcompat.py next to your "
                         "script. Its API:\n" + know.vbc_api())
                log({"vbcompat": True})
            if os.environ.get("KIT") == "1":
                # KIT: tested helper modules for the other domains, same idea as vbcompat (call, do not re-derive):
                # pwkit (Playwright waits on state, read-after-open, collect pages, submit once) and sqlkit (all-or-
                # nothing transactions, executescript replacement). Ports of q_browser_export / q_browser_fix /
                # q_db_migrate on them pass the hidden checks.
                here = os.path.dirname(os.path.abspath(__file__))
                for key, mod, where, how in (
                        ("browser", "pwkit.py", "automation" if (os.path.isdir(os.path.join(workdir, "automation"))
                                                                 or "automation/" in task_text) else "",
                         "next to your script: `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` then "
                         "`from pwkit import *`. Keep `from playwright.sync_api import sync_playwright` in your script too."),
                        ("sqlite", "sqlkit.py", "", "`from sqlkit import *` (run from the project root; inside a package you "
                         "may copy it into the package and use `from .sqlkit import *`).")):
                    if key in keys:
                        rel = os.path.join(where, mod) if where else mod
                        os.makedirs(os.path.join(workdir, where or "."), exist_ok=True)
                        # PWKIT_SRC=pwkit_v1.py: A/B against the previous pwkit (cycle 69), copied under the same name
                        src = os.environ.get("PWKIT_SRC", mod) if mod == "pwkit.py" else mod
                        shutil.copy(os.path.join(here, src), os.path.join(workdir, rel))
                        kmsg += (f"\n\n[harness] {rel} is in the project: a TESTED helper module - use it instead of "
                                 f"writing these parts yourself. Import it {how} Its API:\n" + know.kit_api(src))
                        log({"kit": rel})
                if "webart" in keys:
                    # voxel / three.js scenes: tested voxel kit + one-file builder + headless render report
                    # (vLLM runs text-only here, so render.py describes the picture in numbers)
                    dst = os.path.join(workdir, ".agent", "webkit")
                    shutil.copytree(os.path.join(here, "webkit"), dst, dirs_exist_ok=True,
                                    ignore=shutil.ignore_patterns("__pycache__"))
                    api = open(os.path.join(here, "webkit", "voxelkit.js"), encoding="utf-8").read().split("(() => {")[0]
                    kmsg += ("\n\n[harness] .agent/webkit has a TESTED voxel kit. Write only scene.js (globals THREE and VK; "
                             "first line `// title: ...`), then run\n  python3 .agent/webkit/build.py scene.js index.html && "
                             "python3 .agent/webkit/render.py index.html\nbuild.py makes the single self-contained html "
                             "(three.js import map + kit + your scene); render.py reports errors (scene.js line numbers), "
                             "blank screen, framing, colors, animation, parts standing in water, how many labelled part "
                             "kinds" + (" - and the screenshot is shown to you after every render" if VISION else "")
                             + ". Exit code 137 / 'command killed' from render.py = the machine was busy, not your scene: "
                             "run it again, do NOT shrink the scene. The kit API:\n" + api.replace("// ", "")
                             + "\n\nAn EXAMPLE scene made with the kit (a different subject: use its techniques - layout plan, "
                             "free()/claim() so parts never overlap, a big detailed hero, many labelled parts, movers - not its "
                             "content):\n```js\n" + open(os.path.join(here, "webkit", "example_scene.js"), encoding="utf-8").read()
                             + "```")
                    log({"kit": ".agent/webkit"})
            if kmsg:
                messages[-1]["content"] = task_text + "\n\n" + kmsg
            log({"know": keys, "chars": len(kmsg)})
        except Exception as e:
            log({"know_error": repr(e)[:300]})
    finished, steps = False, 0
    resume_reply, first_step = None, 1
    if os.environ.get("RESUME_FROM"):
        # continue a saved run from its first finish call (CKPT_DIR below): same messages, state and files
        import pickle
        ck = pickle.load(open(os.path.join(os.environ["RESUME_FROM"], "ckpt.pkl"), "rb"))
        messages, first_step, resume_reply = ck["messages"], ck["step"], ck["reply"]
        seed_dir = st.seed_dir
        for k, v in ck["state"].items():
            setattr(st, k, v)
        st.log, st.feats, st.workdir, st.seed_dir = log, F, workdir, seed_dir   # seed_dir: this profile's copy of the inputs
        for e in os.listdir(workdir):  # keep the directory itself: the sandbox already has it mounted
            p_ = os.path.join(workdir, e)
            shutil.rmtree(p_) if os.path.isdir(p_) and not os.path.islink(p_) else os.remove(p_)
        shutil.copytree(os.path.join(os.environ["RESUME_FROM"], "work"), workdir, symlinks=True, dirs_exist_ok=True)
        log({"resumed_from": os.environ["RESUME_FROM"], "step": first_step})
    try:
        max_steps = 120 if "steps120" in F else 80 if "steps80" in F else MAX_STEPS
        # quick improvement cycles (cycle.py): STEP_CAP and TASK_DEADLINE (seconds) end a task early; the hidden check
        # then judges whatever state it reached, the same way for both profiles being compared
        max_steps = min(max_steps, int(os.environ.get("STEP_CAP") or max_steps))
        deadline = t0 + float(os.environ["TASK_DEADLINE"]) if os.environ.get("TASK_DEADLINE") else None
        st.deadline = deadline
        for steps in range(first_step, max_steps + 1):
            if deadline and time.time() > deadline:
                log({"deadline": steps})
                break
            # THINK_TEMP / AGENT_TEMP (env): the base sampling temperature (0.3 since the llama.cpp days; Gemma 4's card
            # says 1.0). 10-24 step sweep on 77 states: validity 96-97% at every temperature, no repeats even at 0, but
            # agreement between samples 90% at 0 vs 67% at 1.0 and broken calls 0% vs 1%
            # default 0 since 10-24 cycle 33 (schema 3, 12 tasks x 2): 14/24 at 0 vs 6/24 at 0.3, 8 wins 0 losses,
            # mean graded score 0.722 vs 0.619, and rep-to-rep score gap 0.095 vs 0.168
            temp = 0.9 if st.hot else float(os.environ.get("AGENT_TEMP", "0"))
            st.hot = max(0, st.hot - 1)
            v5d = "storm" in F
            cf = "cache" in F
            if v5d and st.broken:
                temp = 0.9  # the same prefix at low temperature reproduces the same runaway call
            try:
                # v7n: a typed think is cheap, so it was called 10+ times in a row (cycle 11 csv_merge: 51 of 80 steps); one
                # think, then an action
                offered = [t for t in tools if t["function"]["name"] != "think"] if ("force_act" in F and st.thinks >= (1 if "think_typed" in F else 2)) else tools
                # THINK_GAP: a fused [think, action] step resets st.thinks, so v7o could think on every step (cycle 23
                # lru_ttl: think on most of 70 steps); after a think, the next THINK_GAP steps offer no think
                gap = int(os.environ.get("THINK_GAP", "0"))
                if gap and "think_fuse" in F and steps - getattr(st, "last_think", -99) <= gap:
                    offered = [t for t in offered if t["function"]["name"] != "think"]
                if "plan_lock" in F and st.todo_only >= 2:  # v7i duration: 80 todo calls in a row, refusals ignored
                    offered = [t for t in offered if t["function"]["name"] != "todo"]
                if "verdict_act" in F:
                    offered = verdict_restrict(st, messages, tools, offered, log)
                q, st.notes = view(messages, st, cf), ""
                if "slots" in F:
                    st.notes, q = slot_notes(q, st, offered, temp)
                    log({"notes": st.notes[:1600], "rejects": getattr(st, "notes_rejects", 0), "unresolved": getattr(st, "notes_bad", None)})
                    st.notes_bad = None
                    act = str((getattr(st, "notes_d", None) or {}).get("action", ""))
                    if "unified" in F and act.startswith("restore ") and act[8:] in st.seed_bytes:
                        rp = act[8:]
                        with open(os.path.join(workdir, rp), "wb") as fh:
                            fh.write(st.seed_bytes[rp])
                        track(st, "restore", {}, "")
                        st.ran, st.full = {}, {}
                        log({"restored": rp})
                        messages.append({"role": "assistant", "content": st.notes, "notes_len": len(st.notes)})
                        messages.append({"role": "user", "content": f"[harness] {rp} was restored to the original version given with the task."})
                        continue
                if resume_reply is not None:  # stage 2 of the fast loop: replay the saved finish call, then go on live
                    ch, resume_reply = {"message": resume_reply}, None
                else:
                  st.t_llm0 = time.time()
                  ch = (chat_stream if {"think_abort", "think_jev", "think_typed", "think_fuse", "think_judge"} & F else base.chat)(q, offered, max_tokens=(1536 if v5d and st.broken else 4096), temperature=temp,
                               **({"think_stop": jev_decided} if "think_jev" in F else {}),
                               **({"typed": True} if {"think_typed", "think_fuse"} & F else {}),
                               **({"fuse": True, "workdir": workdir} if "think_fuse" in F else {}),
                               **({"judge": True} if "think_judge" in F else {}),
                               # the action step must be a tool call (v8u cmd_registry: it echoed its notes as text 3x)
                               extra={"tool_choice": "required"} if "unified" in F else None)
            except base.ContextFull as e:
                log({"context_full": str(e)[:200]})
                # v8u region_totals: numeric CSV reads overflowed even after one halving (83754 tokens both times)
                if int(st.compact) >= (3 if {"unified", "fixes"} & F else 1):
                    raise
                st.compact = int(st.compact) + 1  # mask older calls and outputs down to half the limit again, then retry
                continue
            except base.BrokenToolCall as e:
                log({"broken_tool_call": str(e)[:300]})
                # a harness stop for comment reasoning is not a broken call: counting it cut the next calls to 1536
                # tokens (v5d), so a normal 5000-char file was cut too, and so on (cycle 42 vba_sales: 9 broken calls)
                st.broken += 0 if str(e).startswith("comment reasoning") else 1
                msg = ("[harness] Your last tool call was cut off or invalid JSON, so nothing ran. "
                       "Write big files in parts (write_file, then mode=\"append\") and keep each call short.")
                if str(e).startswith("comment reasoning"):
                    msg = ("[harness] Your last " + str(e).split(" inside ")[1].split(" (")[0] + " call was stopped and "
                           "nothing was written: it had 25 comment lines in a row, i.e. reasoning written as code comments. "
                           "Decide first (think), then write only the code, with short comments.")
                    messages.append({"role": "user", "content": msg})
                    continue
                if v5d:
                    msg = ("[harness] Your last tool call was cut off (it grew past the length limit), so nothing ran. "
                           "Do not write your reasoning as comments inside code or commands. Make the call short: "
                           "at most about 60 lines of content per write_file; continue with mode=\"append\".")
                    if messages[-1]["role"] == "user" and str(messages[-1]["content"]).startswith("[harness] Your last tool call was cut off"):
                        continue  # do not stack the same warning
                messages.append({"role": "user", "content": msg})
                continue
            st.broken = 0
            m = ch["message"]
            calls = m.get("tool_calls") or []
            now_ = time.time()
            # where a step's time goes: llm_s = waiting for the model, other_s = everything since the previous reply
            log({"step": steps, "content": (m.get("content") or "")[:2000], "calls": [(c["function"]["name"], c["function"]["arguments"][:1500]) for c in calls],
                 "llm_s": round(now_ - getattr(st, "t_llm0", now_), 1), **{k: ch[k] for k in ("tok", "rs") if ch.get(k) is not None},
                 "other_s": round(getattr(st, "t_llm0", now_) - getattr(st, "t_reply", getattr(st, "t_llm0", now_)), 1)})
            st.t_reply = now_
            if "slots_check" in F and calls:
                why = plan_mismatch(getattr(st, "notes_d", None), calls, set((st.rec.get("hashes") or {})))
                if why and "unified" in F and allowed_call(st, calls):
                    log({"plan_relabel": why})  # a different action that is also on offer: run it
                    why = None
                st.mismatch = getattr(st, "mismatch", 0) + 1 if why else 0
                # in v8u a call outside the offered actions is never run (the second-try pass-through was exploited:
                # "write test" then overwrote billing/dates.py); older profiles keep the pass-through
                if why and (st.mismatch <= 1 or "unified" in F):
                    log({"plan_mismatch": why})
                    near = [x for x in getattr(st, "acts", ()) if any(p in x for p in re.findall(r"[\w./-]+\.\w+", why))][:6]
                    messages.append({"role": "user", "content": "[harness] Not run: " + why + ". Do the action your notes "
                                     "chose, or if it was wrong, choose again in your next notes."
                                     + (" Offered now for that file: " + ", ".join(near) + "." if near and "unified" in F else "")})
                    continue
            if not calls and (m.get("content") or "").endswith(TEXT_CUT):
                messages.append({"role": "assistant", "content": m["content"]})
                messages.append({"role": "user", "content": "[harness] That reply was plain text, so nothing was written or run. "
                                 "Put file contents in write_file (at most about 60 lines per call, then mode=\"append\") and "
                                 "commands in bash."})
                log({"text_cut": steps})
                continue
            if not calls and "text_finish" in F and (m.get("content") or "").strip() and not re.search(r"<\|?channel|<think|<thought", m.get("content") or ""):
                # a finish written as text only: after a rejected finish the model kept replying "I have completed the
                # task..." with no tool call, and "continue with the tools" was answered the same way 60 times
                # (10-23 v7q three_fix steps 20-80); the second such reply in a row is taken as the finish call
                st.textonly = getattr(st, "textonly", 0) + 1
                if st.textonly >= 2:
                    st.textonly = 0
                    calls = [{"id": f"textfinish{steps}", "type": "function", "function": {
                        "name": "finish", "arguments": json.dumps({"summary": m["content"][:1500]}, ensure_ascii=False)}}]
                    log({"text_finish": steps})
            elif calls:
                st.textonly = 0
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
                skip = ("finish", "todo", "view_image") if "force_act" in F else ("finish", "todo", "think", "view_image")
                # (v8u no longer exempts read_file here: the exemption let reads grow to 48% of all calls vs 13% in v7e;
                # a refused re-read shows the full earlier result again, so elision is not a reason to re-run it)
                if a is not None and "write_dedupe" in F and name == "write_file" and isinstance(a.get("content"), str):
                    # the same content written to the same file again within 10 steps: any write in between clears the
                    # repeat memory above, so alternating or interleaved rewrites were never caught
                    # (10-23 browser_fix and cad_wheel: one write_file 5-7 times in 8 steps, 80 steps used up)
                    try:
                        wp = base.safe_path(str(a.get("path", "")))
                    except ValueError:
                        wp = None   # a path outside /work: the tool itself reports it (10-23 sec_firewall crashed here)
                    wk = (wp, hashlib.sha1(a["content"].encode()).hexdigest(), a.get("mode"))
                    hist = getattr(st, "writes", {})
                    if wp is not None and wk in hist and steps - hist[wk][0] <= 10:
                        notes.append(f"write_file {wk[0]}: you already wrote exactly this content at step {hist[wk][0]}, and the "
                                     f"result then was:\n{base.clip(hist[wk][1], 1500)}\nIt was not written again. Writing the same "
                                     "content cannot change the result: change the content, or check something else first.")
                        log({"write_dedupe": wk[0], "step": steps, "first": hist[wk][0]})
                        continue
                if a is not None and name not in skip and akey(name, a, sem) in st.ran:
                    n, res = st.ran[akey(name, a, sem)]
                    st.ran[akey(name, a, sem)] = (n + 1, res)
                    if "unified" in F and name == "bash":
                        st.rec["rerun_refused"] = st.rec.get("rerun_refused", 0) + 1
                        act = str((getattr(st, "notes_d", None) or {}).get("action", ""))
                        if act.startswith("edit "):  # a repeated bash "edit" (v8u expense: touch tests/__init__.py 3x)
                            st.rec.setdefault("edit_block", set()).add(act[5:])
                    if "unified" in F and name in ("edit_file", "write_file") and a.get("path"):
                        st.rec.setdefault("edit_block", set()).add(base.safe_path(str(a["path"])))
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
                st.todo_only = 0
            elif "plan_lock" in F and all(n == "todo" for _, n, _ in fresh):
                st.todo_only += 1
                if st.todo_only >= 3:
                    open_items = [i["text"] for i in st.todo if i.get("status") != "done"]
                    log({"todo_storm": st.todo_only})
                    messages.append({"role": "user", "content": "[harness] The todo list was not updated: you have only edited it "
                                     f"{st.todo_only} times in a row. Do the first open item now with bash, write_file or edit_file"
                                     + (f": {open_items[0]}" if open_items else "") + "."})
                    continue
            # never put unparsable arguments into the history: llama-server re-parses every past tool call and
            # one broken call there makes every later request fail with the same HTTP 500
            safe = []
            for c, name, a in fresh:
                if a is None:
                    c = dict(c, function=dict(c["function"], arguments=json.dumps({"_harness": "call was cut off or invalid JSON"})))
                elif name == "think" and "think_cap" in F and len(str(a.get("thought", ""))) > 1200:
                    c = dict(c, function=dict(c["function"], arguments=json.dumps(
                        {"thought": str(a["thought"])[:1200] + " [... cut by the harness]"}, ensure_ascii=False)))
                elif name == "todo":
                    # v7i duration: ~60 todo calls of several thousand characters each filled the 64K context
                    items = [{"text": str(i.get("text", ""))[:150], "status": i.get("status", "pending")}
                             for i in (a.get("items") if isinstance(a.get("items"), list) else []) if isinstance(i, dict)][:12]
                    c = dict(c, function=dict(c["function"], arguments=json.dumps({"items": items}, ensure_ascii=False)))
                safe.append(c)
            entry = {"role": "assistant", "content": (st.notes + "\n" if st.notes else "") + (m.get("content") or ""), "tool_calls": safe}
            if "unified" in F and st.notes:
                # keep only the latest notes: older ones were copied forward word for word and kept a wrong guess alive
                # for 40 steps (v8u billing: "infinite loop in periods()", caused by its own test listing an endless generator)
                for old_m in messages:
                    if old_m["role"] == "assistant" and old_m.get("notes_len"):
                        old_m["content"] = old_m["content"][old_m.pop("notes_len"):]
                entry["notes_len"] = len(st.notes) + 1
            if os.environ.get("CKPT_DIR") and not getattr(st, "ckpt_saved", False) and any(n == "finish" for _, n, _ in fresh):
                # save the state just before the first finish is judged, so gate changes can be tried from here
                import copy, pickle
                st.ckpt_saved = True
                d = os.path.join(os.environ["CKPT_DIR"], os.path.basename(os.path.dirname(workdir)))
                shutil.rmtree(d, ignore_errors=True)
                shutil.copytree(workdir, os.path.join(d, "work"), symlinks=True)
                keep = {k: v for k, v in st.__dict__.items() if k not in ("log", "feats", "workdir")}
                try:
                    pickle.dump({"messages": copy.deepcopy(messages), "step": steps, "reply": m, "state": keep}, open(os.path.join(d, "ckpt.pkl"), "wb"))
                except Exception as e:
                    log({"ckpt_error": repr(e)[:300]})
            messages.append(entry)
            done_now = False
            for c, name, a in fresh:
                if name == "think":
                    st.last_think = steps
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
                    if (os.environ.get("EDIT2") == "1" and name == "edit_file" and isinstance(a, dict)
                            and not a.get("old_text") and a.get("new_text") and a.get("path")):
                        try:
                            blk = def_block(open(os.path.join(workdir, base.safe_path(a["path"])), encoding="utf-8").read(),
                                            str(a["new_text"]))
                        except (OSError, ValueError, UnicodeDecodeError):
                            blk = None
                        if blk:
                            a = dict(a, old_text=blk)
                            log({"def_block": a["path"], "lines": blk.count("\n") + 1})
                    obs = missing_args(tools, name, a) if st.v6b else None
                    if (obs and os.environ.get("EDIT3") == "1" and name == "write_file" and isinstance(a, dict)
                            and a.get("content") and not a.get("path")):
                        # 128 of 475 v7o runs lost a whole written file to a missing path (165x, 45 s of decoding
                        # each; cycle 39 db_report: 4x in a row): keep the content, ask only for the path
                        body = str(a["content"])
                        # cycle 40 db_report never used "@kept" (3 misses in a row); 119 of 176 path-less writes were the
                        # spec test, CAD ones were model.py: those two get their path from the harness
                        guess = (".agent/spec_test.py" if re.search(r"\bunittest\b|\bdef test_|^\s*assert ", body, re.M)
                                 else "model.py" if re.match(r"\s*(import cadquery|from cadquery)", body) else None)
                        if guess:
                            a = dict(a, path=guess)
                            st.path_note = (f"\n[harness] Your write_file had no path; the harness wrote it to {guess} "
                                            f"(from what it contains). Say so if it belongs elsewhere.")
                            obs = None
                            log({"path_guessed": guess, "chars": len(body)})
                        else:
                            st.kept = body
                            obs = (f"error: write_file needs 'path'. Nothing was written, but your content ({len(st.kept)} "
                                   f"chars) is KEPT: call write_file with the path and content \"@kept\" to write it "
                                   f"without repeating it.")
                            log({"kept_content": len(st.kept)})
                    if obs is None and name == "todo" and "plan_lock" in F and any(
                            len(str(i.get("text", ""))) > 200 for i in (a.get("items") or []) if isinstance(i, dict)):
                        # v7i duration: the model reasoned inside todo item texts (thousands of characters per call)
                        obs = ("error: todo items must be short (one line, under 15 words each). Nothing was saved. "
                               "Put reasoning in the think tool, then set a short todo list.")
                        log({"todo_too_long": True})
                    if obs is None and name == "think" and "plan_lock" in F:
                        obs = plan_lock(st, a, withheld=st.thinks >= 2)
                        if obs:
                            log({"plan_lock": obs[:200]})
                    if obs is None:
                        try:
                            obs = run_tool(box, workdir, st, name, a)
                        except Exception as e:
                            obs = f"error: {type(e).__name__}: {e}"
                    if os.environ.get("THINK_AUTOCHECK") == "1" and a is not None:
                        obs = autocheck(box, st, name, a, obs, log)
                    if VISION and name == "bash" and a is not None and "render.py" in str(a.get("command", "")):
                        # VISION: every render is also SHOWN (vLLM lanes now accept images): the model judges the
                        # picture itself, not only render.py's numbers
                        m_png = re.search(r"^screenshot: (\S+)", obs, re.M)
                        png = m_png and os.path.join(workdir, os.path.relpath(m_png.group(1), "/work") if m_png.group(1).startswith("/work") else m_png.group(1))
                        if png and os.path.exists(png):
                            st.pending_image = png
                            obs += ("\n[harness] The screenshot is shown in the next message. Look at it: is the hero big and "
                                    "detailed, is the garden full, is anything floating, cut off, in the water or ugly? Fix what you see.")
                    if name not in ("todo",) if "force_act" in F else name not in ("todo", "think"):
                        st.ran[akey(name, a, "semantic_repeat" in F)] = (1, one_line(obs))
                    if "write_dedupe" in F and name == "write_file" and a is not None and isinstance(a.get("content"), str) \
                            and not obs.startswith("error"):
                        if not hasattr(st, "writes"):
                            st.writes = {}
                        try:
                            st.writes[(base.safe_path(str(a.get("path", ""))), hashlib.sha1(a["content"].encode()).hexdigest(), a.get("mode"))] = (steps, obs)
                        except ValueError:
                            pass
                    if ("slots_check" in F or "fixes" in F) and a is not None:
                        track(st, name, a, obs)
                        st.full[akey(name, a, "semantic_repeat" in F)] = obs
                        # a later change can make an earlier command worth re-running
                        if name in ("write_file", "edit_file") and not obs.startswith("error") and st.changed:
                            st.ran, st.full = {}, {}  # files changed: every earlier command may give a new result
                if notes:
                    obs += "\n[harness] " + " ".join(notes)
                    notes = []
                messages.append({"role": "tool", "tool_call_id": c.get("id", ""), "content": obs})
                log({"obs": obs[:1500]})
            if st.pending_image:
                import base64, mimetypes
                mime = mimetypes.guess_type(st.pending_image)[0] or "image/png"
                data = base64.b64encode(open(st.pending_image, "rb").read()).decode()
                messages.append({"role": "user", "content": [
                    {"type": "text", "text": f"[harness] {os.path.relpath(st.pending_image, workdir)}:"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}}]})
                log({"image": os.path.relpath(st.pending_image, workdir)})
                st.pending_image = None
            if done_now:
                finished = True
                break
            # files changed by any tool (bash heredocs, scripts, mv/rm) make earlier results stale; only write/edit
            # used to reset them, so v7h h_md got a pre-write ModuleNotFoundError replayed 60+ times
            snap_now = snapshot(workdir)
            if st.files_snap is not None and snap_now != st.files_snap:
                st.ran, st.full = {}, {}
            st.files_snap = snap_now
            if os.environ.get("MIDGATE") == "1" and st.seed_dir and getattr(st, "deadline", None):
                midgate_tick(st, task_text, workdir, messages, log)
            if "midfacts" in F and steps in (30, 55) and st.seed_dir:
                # most 80-step failures never reached finish, so the evidence gate never ran (10-23 v7q run 2: 7 of 12
                # failures); the same harness-collected facts are shown mid-run, without any judgment
                try:
                    import evidence
                    t1 = time.time()
                    facts = evidence.collect(workdir, st.seed_dir, task_text)
                    messages.append({"role": "user", "content": f"[harness] Step {steps} of 80. The harness ran the task's "
                                     "commands on a fresh copy of your files and collected these facts:\n<facts>\n"
                                     + facts[:5000] + "\n</facts>\nCompare them with the task and docs, fix what they show is "
                                     "still wrong, and call finish when the result is right."})
                    st.hot = 1
                    log({"midfacts": steps, "seconds": round(time.time() - t1, 1), "chars": len(facts)})
                except Exception as e:
                    log({"midfacts_error": repr(e)[:300]})
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
        if {"unified", "fixes"} & F:
            try:
                end_guard(st, box, log)
            except Exception as e:  # the guard must never break a run
                log({"end_guard_error": repr(e)[:300]})
        box.close()
    return {"steps": steps, "finished": finished, "seconds": round(time.time() - t0, 1), "judge": st.judge_log}
