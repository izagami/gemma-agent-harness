"""Hidden check: Settings vs the original legacy module, original CLI vs migrated CLI, no global state."""
import contextlib, importlib.util, io, os, shutil, subprocess, sys, tempfile

PROJ = sys.argv[1]
T = tempfile.mkdtemp()
os.chdir(T)
sys.path.insert(0, PROJ)
spec = importlib.util.spec_from_file_location("legacy_ref", "/check/legacy_settings.py")
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
from tool.settings import Settings  # noqa: E402
from tool import fmt, log, manifest, report, scanner  # noqa: E402


def w(p, text):
    os.makedirs(os.path.dirname(os.path.abspath(p)), exist_ok=True)
    with open(p, "wb" if isinstance(text, bytes) else "w") as f:
        f.write(text)


def outcome(fn, *a):
    try:
        r = fn(*a)
        return ("ok", type(r).__name__, r)
    except Exception as e:  # noqa: BLE001
        return ("exc", type(e).__name__, str(e))


INIS = {
    "a.ini": '[DEFAULT]\nchecksums = off\nlevel = 3\n[Backup]\nName = "nightly run"\nexclude = *.tmp, ,build/*,\n   *.log\nmax_size = 1_500\n'
             '[report]\nunits = SI\ndecimals = 2\ntop = -1\nshow_largest = On\nalign = right\ntitle = "  spaced  "\n[mail_out]\nfrom_addr = a@b\n',
    "b.ini": "[general]\nverbose = yes\nlog_prefix = >>\n[report]\nunits = b\ntop = 0x10\ngroup_by = dir\n[x]\nflag = maybe\nnum = 12abc\nempty =\nquoted = \"\"\n",
    "c.ini": "[report]\npct = 50%\nlist = one\n  two , three\n  ,\n",
    "tool.ini": "[report]\ntitle = from cwd tool.ini\n",
    "envcfg.ini": "[report]\ntitle = from TOOL_CONFIG\n[backup]\norder = size\n",
}
for k, v in INIS.items():
    w(os.path.join(T, k), v)

KEYS = ["backup.name", "backup.exclude", "backup.max_size", "backup.checksums", "backup.level", "BACKUP.NAME",
        "report.units", "report.decimals", "report.top", "report.show_largest", "report.align", "report.title",
        "report.group_by", "report.pct", "report.list", "mail_out.from_addr", "general.verbose", "general.log_prefix",
        "x.flag", "x.num", "x.empty", "x.quoted", "nosuch.key", "report.checksums", "default.level", "a_b.c_d", "env.only"]
CASES = [
    ("a.ini", {}, {}),
    ("a.ini", {"TOOL_REPORT__UNITS": "", "TOOL_BACKUP__NAME": '  "env name" ', "TOOL_A_B__C_D": "x", "TOOL_CONFIG": "b.ini"}, {}),
    ("a.ini", {"TOOL_REPORT__TOP": "7"}, {"Report.Top": "  9 ", "report.title": "", "new.key": "v"}),
    ("b.ini", {"TOOL_ENV__ONLY": "true", "TOOL_X__FLAG": "OFF", "TOOLX__Y": "no", "TOOL_NOSEP": "1", "TOOL___Z": "3"}, {}),
    ("c.ini", {}, {"x.num": "1_0_0"}),
    (None, {}, {}),
    (None, {"TOOL_CONFIG": "envcfg.ini"}, {}),
    (None, {"TOOL_CONFIG": "missing.ini", "TOOL_REPORT__UNITS": "iec"}, {}),
    ("missing.ini", {}, {}),
    ("b.ini", {"TOOL_GENERAL__VERBOSE": ""}, {"general.verbose": ""}),
]
n = 0
for path, env, ov in CASES:
    L.clear_overrides()
    leg = outcome(L.reload, path, dict(env))
    new = outcome(lambda: Settings.load(path, dict(env), dict(ov)))
    assert leg[0] == new[0], (path, env, leg, new)
    if leg[0] == "exc":
        assert leg[1:] == new[1:], (path, leg, new)
        n += 1
        continue
    s = new[2]
    for k, v in ov.items():
        L.set_override(k, v)
    assert L.items() == s.items(), (path, env, ov, L.items(), s.items())
    for k in KEYS:
        for meth in ("get", "get_int", "get_bool", "get_list"):
            for dflt in ((), (None,), ("D",), (["d"],), (0,)):
                a = outcome(getattr(L, meth), k, *dflt)
                b = outcome(getattr(s, meth), k, *dflt)
                assert a == b, f"{meth}({k!r}, {dflt}) with ini={path} env={env} overrides={ov}: legacy {a} != new {b}"
                n += 1
# default env = os.environ at load time
os.environ["TOOL_ZZ__TOP"] = "abc"
assert Settings.load(os.path.join(T, "c.ini")).get("zz.top") == "abc"
del os.environ["TOOL_ZZ__TOP"]
print(f"settings: {n} getter comparisons OK")

# --- side by side, no global state
src = os.path.join(T, "src")
for rel, size in [("a.py", 10), ("b.PY", 2500), ("lib/c.py", 4096), ("lib/.cache", 50), ("build/out.tmp", 3000),
                  ("docs/x.log", 1200), ("docs/guide.md", 7000), ("noext", 1), (".env", 3), ("z.tmp", 5)]:
    w(os.path.join(src, rel), b"y" * size)
s1 = Settings.load(os.path.join(T, "a.ini"), {})
s2 = Settings.load(os.path.join(T, "b.ini"), {"TOOL_REPORT__TITLE": "Two"})
s3 = Settings.load(None, {}, {"report.units": "iec", "backup.include_hidden": "1", "backup.order": "size"})


def legacy_eval(path, env, ov, fn):
    """Run fn() against the ORIGINAL modules configured through the legacy globals."""
    mods = {}
    for m in ("legacy_settings", "log", "fmt", "scanner", "manifest", "report"):
        sp = importlib.util.spec_from_file_location(f"tool.{m}", f"/check/orig/tool/{m}.py")
        mods[m] = importlib.util.module_from_spec(sp)
    saved = {k: sys.modules.get(k) for k in list(sys.modules) if k == "tool" or k.startswith("tool.")}
    try:
        import types
        pkg = types.ModuleType("tool"); pkg.__path__ = ["/check/orig/tool"]
        sys.modules["tool"] = pkg
        for m, mod in mods.items():
            sys.modules[f"tool.{m}"] = mod; setattr(pkg, m, mod)
        for m in ("legacy_settings", "log", "fmt", "scanner", "manifest", "report"):
            mods[m].__spec__.loader.exec_module(mods[m])
        mods["legacy_settings"].clear_overrides()
        mods["legacy_settings"].reload(path, env)
        for k, v in ov.items():
            mods["legacy_settings"].set_override(k, v)
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            r = outcome(fn, mods)
        return r, err.getvalue()
    finally:
        for k in [k for k in sys.modules if k == "tool" or k.startswith("tool.")]:
            del sys.modules[k]
        sys.modules.update({k: v for k, v in saved.items() if v is not None})


CFG = {id(s1): (os.path.join(T, "a.ini"), {}, {}), id(s2): (os.path.join(T, "b.ini"), {"TOOL_REPORT__TITLE": "Two"}, {}),
       id(s3): (None, {}, {"report.units": "iec", "backup.include_hidden": "1", "backup.order": "size"})}
OUT = os.path.join(T, "out")


def ops(s):
    """(description, new-api call, legacy call) triples."""
    return [
        ("scan", lambda: scanner.scan(src, settings=s), lambda m: m["scanner"].scan(src)),
        ("size", lambda: [fmt.size(x, settings=s) for x in (0, 999, 1000, 1023, 1024, 1536, 10**6, 5 * 2**30)],
         lambda m: [m["fmt"].size(x) for x in (0, 999, 1000, 1023, 1024, 1536, 10**6, 5 * 2**30)]),
        ("pad", lambda: [fmt.pad("ab", 6, settings=s), fmt.pad("ab", 6, align="right", settings=s)],
         lambda m: [m["fmt"].pad("ab", 6), m["fmt"].pad("ab", 6, align="right")]),
        ("groups", lambda: report.groups(scanner.scan(src, settings=s), settings=s), lambda m: m["report"].groups(m["scanner"].scan(src))),
        ("report", lambda: report.render(scanner.scan(src, settings=s), settings=s), lambda m: m["report"].render(m["scanner"].scan(src))),
        ("manifest", lambda: manifest.render(scanner.scan(src, settings=s), settings=s), lambda m: m["manifest"].render(m["scanner"].scan(src))),
        ("write", lambda: open(manifest.write(scanner.scan(src, settings=s), OUT, settings=s)).read(),
         lambda m: open(m["manifest"].write(m["scanner"].scan(src), OUT)).read()),
        ("log", lambda: log.info("hello", settings=s), lambda m: m["log"].info("hello")),
    ]


def norm(r):  # dataclass Entry objects from two different modules: compare as tuples
    if r[0] == "ok" and isinstance(r[2], list):
        return (r[0], r[1], [tuple(vars(x).values()) if hasattr(x, "__dataclass_fields__") else x for x in r[2]])
    return r


expected = {}
for s in (s1, s2, s3):
    for name, _, leg in ops(s):
        expected[(id(s), name)] = legacy_eval(*CFG[id(s)], leg)
order = [(s, i) for i in range(8) for s in (s2, s1, s3)] + [(s, i) for s in (s3, s1, s2) for i in reversed(range(8))]
for s, i in order:
    name, new, _ = ops(s)[i]
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        got = outcome(new)
    exp = expected[(id(s), name)]
    assert (norm(got), err.getvalue()) == (norm(exp[0]), exp[1]), f"{name} with settings {CFG[id(s)]}:\n got {got} {err.getvalue()!r}\n exp {exp}"
print("side-by-side: OK")

# --- CLI: original vs migrated, byte for byte
def cli(pp, args, env, cwd):
    e = {k: v for k, v in os.environ.items() if not k.startswith("TOOL_")}
    e.update(env, PYTHONPATH=pp, PYTHONDONTWRITEBYTECODE="1")
    outd = os.path.join(T, "cliout")
    shutil.rmtree(outd, ignore_errors=True)
    r = subprocess.run([sys.executable, "-m", "tool", *args], cwd=cwd, env=e, capture_output=True, timeout=20)
    files = {}
    if os.path.isdir(outd):
        for f in sorted(os.listdir(outd)):
            files[f] = open(os.path.join(outd, f), "rb").read()
    return r.returncode, r.stdout, r.stderr, files


OD = os.path.join(T, "cliout")
RUNS = [
    (["--config", "a.ini", "scan", "src"], {}),
    (["--config", "a.ini", "report", "src"], {}),
    (["--config", "a.ini", "backup", "src", OD], {"TOOL_BACKUP__ORDER": "size"}),
    (["--config", "b.ini", "report", "src"], {}),
    (["--config", "b.ini", "--set", "report.top=3", "report", "src"], {}),
    (["--config", "b.ini", "--set", "report.top=2", "--set", "report.group_by=ext", "report", "src"], {"TOOL_GENERAL__VERBOSE": "0"}),
    (["--config", "c.ini", "show-config"], {"TOOL_A_B__C_D": " v ", "TOOL_REPORT__LIST": ""}),
    (["--config", "a.ini", "--set", "Report.Units=bogus", "report", "src"], {}),
    (["--config", "a.ini", "--set", "backup.order=weird", "backup", "src", OD], {}),
    (["--config", "a.ini", "--set", "backup.include_hidden=sure", "scan", "src"], {}),
    (["--config", "nope.ini", "--set", "bad", "show-config"], {}),
    (["--set", "bad", "show-config"], {}),
    (["show-config"], {}),
    (["report", "src"], {"TOOL_CONFIG": "envcfg.ini"}),
    (["backup", "src", OD], {"TOOL_CONFIG": "envcfg.ini", "TOOL_BACKUP__NAME": "envname", "TOOL_GENERAL__VERBOSE": "on"}),
    (["--config", "b.ini", "--set", "general.verbose=", "scan", "src"], {}),
    (["--config", "b.ini", "scan", "src"], {"TOOL_GENERAL__VERBOSE": ""}),
    (["--config", "a.ini", "--set", "report.decimals=3", "--set", "report.show_largest=no", "report", "src"], {"TOOL_REPORT__UNITS": "iec"}),
]
for args, env in RUNS:
    a = cli("/check/orig", args, env, T)
    b = cli(PROJ, args, env, T)
    assert a == b, f"CLI differs for {args} env={env}:\n original {a}\n migrated {b}"
print(f"cli: {len(RUNS)} runs identical")
shutil.rmtree(T)
