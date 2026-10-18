import os, subprocess, sys, tempfile
WORK = sys.argv[1] if len(sys.argv) > 1 else "/work"
D = tempfile.mkdtemp()

def w(name, text):
    p = os.path.join(D, name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w", encoding="utf-8").write(text)

def run(*argv, env=None, cwd=None):
    e = {k: v for k, v in os.environ.items() if k != "TS_CONFIG"}
    e["PYTHONPATH"] = WORK
    e.update(env or {})
    r = subprocess.run([sys.executable, "-m", "ts", *argv], cwd=cwd or D, env=e, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr

def eq(got, exp):
    assert got == exp, (got, exp)

# --- v1 still works
eq(run("add", "2026-09-03", "alpha", "10m"), (0, "added: 2026-09-03 alpha 0:10\n", ""))
eq(run("list"), (0, "2026-09-03  alpha  0:10\n", ""))
os.remove(os.path.join(D, "entries.tsv"))

# --- data for invoices
w("data/e.tsv", "".join(f"{l}\n" for l in [
    "2026-09-03\talpha\t10\t",
    "2026-09-01\talpha\t90\tdesign review",
    "2026-08-31\talpha\t60\taugust",
    "2026-09-01\tbeta\t30\tother",
    "2026-09-30\talpha\t7\tlate fix",
    "2026-09-01\talpha\t1\tsecond same day",
    "2026-10-01\talpha\t60\toctober",
]))
w("main.conf", 'data = data/e.tsv\n[project.alpha]\nrate = 6000\nname = "Alpha Corp"\n[project.beta]\nrate = 1001\n')
eq(run("--config", "main.conf", "invoice", "alpha", "--month", "2026-09"), (0,
   "Invoice: Alpha Corp (alpha) 2026-09\n2026-09-01  1:30  9,000  design review\n2026-09-01  0:01  100  second same day\n"
   "2026-09-03  0:10  1,000\n2026-09-30  0:07  700  late fix\nTotal: 1:48  10,800\n", ""))
eq(run("--config", "main.conf", "invoice", "beta", "--month", "2026-09"), (0,
   "Invoice: beta (beta) 2026-09\n2026-09-01  0:30  501  other\nTotal: 0:30  501\n", ""))
eq(run("--config", "main.conf", "invoice", "alpha", "--month", "2026-07"), (0, "Invoice: Alpha Corp (alpha) 2026-07\nTotal: 0:00  0\n", ""))
for bad in ["2026-9", "2026-13", "202609", "2026-00", "x"]:
    eq(run("--config", "main.conf", "invoice", "alpha", "--month", bad), (2, "", f"error: invalid month: {bad}\n"))
eq(run("--config", "main.conf", "invoice", "Alpha", "--month", "2026-09"), (2, "", "error: invalid project: Alpha\n"))
eq(run("--config", "main.conf", "invoice", "gamma", "--month", "2026-09"), (1, "", "error: no rate for project: gamma\n"))
assert run("--config", "main.conf", "invoice", "alpha")[0] == 2

# round_to, half-up, thousands
w("r.conf", "data = data/e.tsv\n[invoice]\nround_to = 15\n[project.alpha]\nrate = 12345\n")
eq(run("--config", "r.conf", "invoice", "alpha", "--month", "2026-09"), (0,
   "Invoice: alpha (alpha) 2026-09\n2026-09-01  1:30  18,518  design review\n2026-09-01  0:15  3,086  second same day\n"
   "2026-09-03  0:15  3,086\n2026-09-30  0:15  3,086  late fix\nTotal: 2:15  27,776\n", ""))
w("r2.conf", "data = data/e.tsv\n[invoice]\nround_to = 0\n[project.alpha]\nrate = 1\n")
eq(run("--config", "r2.conf", "invoice", "alpha", "--month", "2026-09"), (2, "", "error: config: bad invoice.round_to\n"))
w("r3.conf", "data = data/e.tsv\n[project.alpha]\nrate = 12.5\n")
eq(run("--config", "r3.conf", "invoice", "alpha", "--month", "2026-09"), (2, "", "error: config: bad rate for project: alpha\n"))
w("r4.conf", "data = data/e.tsv\n[project.alpha]\nrate = -5\n")
eq(run("--config", "r4.conf", "invoice", "alpha", "--month", "2026-09"), (2, "", "error: config: bad rate for project: alpha\n"))

# --- TS_CONFIG priority
w("envdir/env.conf", "data = ../data/e.tsv\n")
w("ts.conf", "data = nothing.tsv\n")
eq(run("total", "--project", "beta", env={"TS_CONFIG": "envdir/env.conf"}), (0, "beta  0:30\nTOTAL  0:30\n", ""))
eq(run("total", "--project", "beta", env={"TS_CONFIG": ""}), (0, "no entries\n", ""))
eq(run("--config", "main.conf", "total", "--project", "beta", env={"TS_CONFIG": "nope.conf"}), (0, "beta  0:30\nTOTAL  0:30\n", ""))
eq(run("list", env={"TS_CONFIG": "nope.conf"}), (2, "", "error: config: not found: nope.conf\n"))
os.remove(os.path.join(D, "ts.conf"))

# --- @include
w("inc/main.conf", "data = ../data/e.tsv\n[project.alpha]\nrate = 1\n@include parts/rates.conf\nname = Overridden\n[alias]\n@include parts/alias.conf\n")
w("inc/parts/rates.conf", "  @include   more/name.conf  \n[project.alpha]\nrate = 6000\n")
w("inc/parts/more/name.conf", "name = top level only\n[project.alpha]\nname = From Include\n")
w("inc/parts/alias.conf", "[alias]\nsep = invoice alpha --month 2026-09\n")
eq(run("--config", "inc/main.conf", "invoice", "alpha", "--month", "2026-08"), (0,
   "Invoice: Overridden (alpha) 2026-08\n2026-08-31  1:00  6,000  august\nTotal: 1:00  6,000\n", ""))
out = run("--config", "inc/main.conf", "sep")
eq(out[0], 0); assert out[1].startswith("Invoice: Overridden (alpha) 2026-09\n"), out
w("inc2/main.conf", "data = ../data/e.tsv\n[project.beta]\n@include r.conf\nrate = 10\n")
w("inc2/r.conf", "rate = 99999\nname = Top\n")
eq(run("--config", "inc2/main.conf", "invoice", "beta", "--month", "2026-09"), (0,
   "Invoice: beta (beta) 2026-09\n2026-09-01  0:30  5  other\nTotal: 0:30  5\n", ""))
# errors
w("e1.conf", "a = 1\n\n@include missing.conf\n")
eq(run("--config", "e1.conf", "list"), (2, "", "error: config: line 3: include not found: missing.conf\n"))
w("e2.conf", "@include e2.conf\n")
eq(run("--config", "e2.conf", "list"), (2, "", "error: config: line 1: include cycle: e2.conf\n"))
w("c/a.conf", "x = 1\n@include b/b.conf\n")
w("c/b/b.conf", "# b\n@include ../a.conf\n")
eq(run("--config", "c/a.conf", "list"), (2, "", "error: config: b/b.conf: line 2: include cycle: ../a.conf\n"))
w("n/main.conf", "@include sub/a.conf\n")
w("n/sub/a.conf", "x = 1\n\n@include b.conf\n")
w("n/sub/b.conf", "y = 2\nbogus line\n")
eq(run("--config", "n/main.conf", "list"), (2, "", "error: config: b.conf: line 2: expected key = value\n"))
os.remove(os.path.join(D, "n/sub/b.conf"))
eq(run("--config", "n/main.conf", "list"), (2, "", "error: config: sub/a.conf: line 3: include not found: b.conf\n"))
w("e3.conf", "ok = 1\n   @include   \n")
eq(run("--config", "e3.conf", "list"), (2, "", "error: config: line 2: bad include\n"))
w("twice/m.conf", "@include s.conf\n@include s.conf\ndata = ../data/e.tsv\n")
w("twice/s.conf", "k = v\n")
eq(run("--config", "twice/m.conf", "total", "--project", "beta"), (0, "beta  0:30\nTOTAL  0:30\n", ""))

# --- aliases
w("al.conf", "data = data/e.tsv\n[alias]\nwk = list --project beta\ntw = total --project beta\n"
   "list = total\nchain = wk\nq = list --project 'al pha'\n")
eq(run("--config", "al.conf", "wk"), (0, "2026-09-01  beta  0:30  other\n", ""))
eq(run("--config=al.conf", "tw"), (0, "beta  0:30\nTOTAL  0:30\n", ""))
eq(run("--config", "al.conf", "tw", "--project", "alpha"), (0, "alpha  3:48\nTOTAL  3:48\n", ""))
eq(run("--config", "al.conf", "list", "--project", "beta"), (0, "2026-09-01  beta  0:30  other\n", ""))
assert run("--config", "al.conf", "chain")[0] == 2
eq(run("--config", "al.conf", "q"), (0, "no entries\n", ""))
eq(run("tw", env={"TS_CONFIG": "al.conf"}), (0, "beta  0:30\nTOTAL  0:30\n", ""))
w("ts.conf", "data = data/e.tsv\n[alias]\nb = list --project beta\n")
eq(run("b"), (0, "2026-09-01  beta  0:30  other\n", ""))
print("ok")
