"""Hidden check: refactored invtool == original invtool byte for byte; plugin modules are discovered."""
import base64, json, os, shutil, subprocess, sys, tempfile

PROJ = sys.argv[1]
T = tempfile.mkdtemp()


def run(pp, data_src, script):
    """Run a sequence of invocations on a fresh copy of data_src; return outputs + final files."""
    w = os.path.join(T, "w")
    shutil.rmtree(w, ignore_errors=True)
    os.makedirs(os.path.join(w, "data"))
    for suffix in ("", ".history"):
        if os.path.exists(data_src + suffix):
            shutil.copy(data_src + suffix, os.path.join(w, "data", "inventory.csv" + suffix))
    env = dict(os.environ, PYTHONPATH=pp, PYTHONDONTWRITEBYTECODE="1")
    sf = os.path.join(T, "script.json")
    json.dump(script, open(sf, "w"))
    r = subprocess.run([sys.executable, "/check/driver.py", w, sf], env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-2000:]
    res = [(tuple(a), c, base64.b64decode(o), base64.b64decode(e)) for a, c, o, e in json.loads(r.stdout)]
    files = {}
    for root, _, fs in os.walk(w):
        for f in sorted(fs):
            p = os.path.join(root, f)
            files[os.path.relpath(p, w)] = open(p, "rb").read()
    return res, files


D1, D2 = "/check/inventory.csv", "/check/inv2.csv"
SCRIPTS = [
    (D1, [[], ["help"], ["help", "adjust"], ["help", "nope"], ["help", "a", "b"], ["list"], ["list", "--sort", "qty"],
          ["list", "--sort=name"], ["list", "--location", "shelf2", "--sort", "value"], ["list", "--sort", "bogus"],
          ["list", "--frob"], ["list", "x"], ["show", "e-500"], ["show"], ["value"], ["value", "--by", "location"],
          ["value", "--by", "sku"], ["low"], ["low", "--threshold", "50"], ["low", "--threshold", "0"], ["low", "--threshold", "x"],
          ["search", "ボール"], ["search", "zzz"], ["search", " "], ["export"], ["export", "--format", "tsv"],
          ["export", "--format=json"], ["export", "--format", "xml"], ["history", "A-101"], ["history", "E-500"],
          ["history", "A-101", "--limit", "0"], ["nosuch"], ["--data"], ["--database", "x"]]),
    (D1, [["add", "f-1", "封筒", "10", "5.5"], ["add", "F-1", "dup", "1", "1"], ["add", "g!1", "x", "1", "1"],
          ["add", "g-2", " ", "1", "1"], ["add", "g-3", "x", "-1", "1"], ["add", "g-4", "x", "1", "1.234"],
          ["add", "g-5", "x", "zz", "1"], ["add", "g-6", "テープ", "0", "1200", "--location", "back"], ["add", "g-7"],
          ["adjust", "f-1", "-8", "--reason", "sold\tout"], ["adjust", "f-1", "-3"], ["adjust", "f-1", "0"], ["adjust", "f-1", "+20"],
          ["adjust", "nope", "1"], ["move", "f-1", "shelf2"], ["move", "F-1", "SHELF2"], ["remove", "f-1"], ["remove", "g-6"],
          ["remove", "a-100", "--force"], ["history", "F-1"], ["history", "f-1", "--limit=2"], ["list"], ["value", "--by", "location"],
          ["export", "--format", "json"]]),
    (D2, [["list"], ["list", "--sort", "value"], ["value"], ["value", "--by", "location"], ["low"], ["show", "p-3"],
          ["search", "CLIP"], ["export"], ["export", "--format", "json"], ["history", "K-1"], ["adjust", "Q-9", "-5"],
          ["remove", "q-9"], ["move", "p-3", "main"], ["add", "z-9", "Zeta, \"quoted\"", "1", "1000000"], ["list", "--sort", "name"],
          ["value"], ["--data=data/other.csv", "list"], ["--data", "data/new/inv.csv", "add", "n-1", "new", "2", "3"],
          ["--data", "data/new/inv.csv", "list"]]),
]
# tasks_v8g items: one per invocation (77), one per "data files equal after the script" (3), plugin checks (6)
ITEMS = [0, 0]
FAILS = []


def item(ok, msg=""):
    ITEMS[1] += 1
    ITEMS[0] += bool(ok)
    if not ok:
        FAILS.append(msg)


def safe_run(pp, data, script):
    try:
        return run(pp, data, script), ""
    except Exception as x:  # noqa: BLE001 - tasks_v8: the assert in run() ended the script (= failure)
        return None, f"{x!r}"[:600]


n = 0
for data, script in SCRIPTS:
    a = run("/check/orig", data, script)
    b, why = safe_run(PROJ, data, script)
    for k, x in enumerate(a[0]):
        n += 1
        if b is not None and k >= len(b[0]):
            item(True)  # tasks_v8 compared with zip(): invocations past a shorter result list were not checked
            continue
        y = b[0][k] if b is not None else None
        if y is None:
            item(False, f"invtool {' '.join(x[0])}: no result ({why})")
        else:
            item(x == y, f"invtool {' '.join(x[0])} differs:\n original: code={x[1]} out={x[2]!r} err={x[3]!r}\n refactored: code={y[1]} out={y[2]!r} err={y[3]!r}")
    item(b is not None and a[1] == b[1], f"data files differ after {script}:\n original {a[1]}\n refactored {b and b[1]}")
print(f"golden: {n} invocations, {n - len([f for f in FAILS if f.startswith('invtool')])} identical")

# plugin discovery
cmds = os.path.join(PROJ, "invtool", "commands")
copied = []
try:
    for f in ("zz_ping.py", "_private.py"):
        shutil.copy(os.path.join("/check", f), os.path.join(cmds, f))
        copied.append(f)
    res, _ = run(PROJ, D1, [["ping", "a", "b"], ["ping", "fail"], ["help"], ["help", "ping"], ["ping"], ["list", "--sort", "qty"]])
except Exception as x:  # noqa: BLE001
    res = None
    why = f"{x!r}"[:600]
exp_help = run("/check/orig", D1, [["help"]])[0][0][2].decode()
lines = exp_help.splitlines(keepends=True)
i = next(k for k, l in enumerate(lines) if l.startswith("  remove"))
lines.insert(i, "  ping      reply with pong\n")
want = [(0, b"pong a b inventory.csv\n", b""), (3, b"", b"error: ping failed\n"), (0, "".join(lines).encode(), b""),
        (0, b"usage: invtool ping [WORD...]\n\nreply with pong\n", b""), (0, b"pong inventory.csv\n", b"")]
# (tasks_v8 asserted len(res) == 6 first; a result list of another length fails every plugin item here)
good = res is not None and len(res) == 6
for k, exp in enumerate(want):
    if not good:
        item(False, f"plugin: {why if res is None else f'{len(res)} results instead of 6'}")
        continue
    args, *got = res[k]
    item(tuple(got) == exp, f"plugin: invtool {' '.join(args)}: got {got} expected {exp}")
item(good and res[5][1] == 0 and res[5][2] == run("/check/orig", D1, [["list", "--sort", "qty"]])[0][0][2],
     "plugin: list --sort qty differs with plugins present")
for f in copied:
    os.remove(os.path.join(cmds, f))
print("plugin: OK" if not [f for f in FAILS if f.startswith("plugin")] else "plugin: FAILED")
shutil.rmtree(T)
for f in FAILS[:3]:
    print("FAIL", f[:500])
print(f"ITEMS {ITEMS[0]}/{ITEMS[1]}")
sys.exit(1 if FAILS else 0)
