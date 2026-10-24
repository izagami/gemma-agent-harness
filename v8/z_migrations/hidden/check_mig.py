"""Hidden behavioural check for the notes migration runner. Run from anywhere; project = argv[1]."""
import hashlib, os, shutil, sqlite3, subprocess, sys, tempfile

PROJ = sys.argv[1] if len(sys.argv) > 1 else "/work"
T = tempfile.mkdtemp()
ENV = dict(os.environ, PYTHONPATH=PROJ, PYTHONDONTWRITEBYTECODE="1")
ENV.pop("NOTES_DB", None)
N = [0]


def run(*args, env=None):
    r = subprocess.run([sys.executable, "-m", "notes", *args], cwd=T, env=env or ENV, capture_output=True, text=True, timeout=20)
    return r.returncode, r.stdout, r.stderr


def expect(args, code, out=None, err=None, err_prefix=None, env=None):
    N[0] += 1
    got = run(*args, env=env)
    ok = got[0] == code and (out is None or got[1] == out) and (err is None or got[2] == err) \
        and (err_prefix is None or (got[2].startswith(err_prefix) and got[2].count("\n") == 1))
    assert ok, f"#{N[0]} {' '.join(args)}\n expected code={code} out={out!r} err={err if err is not None else err_prefix!r}\n got code={got[0]} out={got[1]!r} err={got[2]!r}"
    return got


def mkdir(name, files):
    d = os.path.join(T, name)
    shutil.rmtree(d, ignore_errors=True)
    os.makedirs(d)
    for f, sql in files.items():
        open(os.path.join(d, f), "w").write(sql)
    return d


def rows(dbp):
    c = sqlite3.connect(dbp)
    r = c.execute("SELECT version, name, checksum FROM schema_migrations ORDER BY version").fetchall()
    c.close()
    return r


def tables(dbp):
    c = sqlite3.connect(dbp)
    r = {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    c.close()
    return r


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def fbytes(p):
    return open(p, "rb").read()


DEF = os.path.join(PROJ, "migrations")
S1, S2 = sha(os.path.join(DEF, "001_initial.sql")), sha(os.path.join(DEF, "002_add_pinned.sql"))
INIT_SQL = open("/check/001_initial.sql").read()

# --- A: default dir (project migrations/, not cwd), fresh db, idempotent, status
os.makedirs(os.path.join(T, "migrations"))  # decoy in cwd: must be ignored
open(os.path.join(T, "migrations", "001_decoy.sql"), "w").write("CREATE TABLE decoy(x);")
a = os.path.join(T, "a.db")
expect(["--db", a, "migrate", "status"], 0, "[ ] 001 initial\n[ ] 002 add_pinned\ncurrent: none\n", "")
assert not os.path.exists(a), "status created the db file"
expect(["--db", a, "migrate", "--dry-run"], 0, "would apply 001 initial\nwould apply 002 add_pinned\n", "")
assert not os.path.exists(a), "--dry-run created the db file"
expect(["--db", a, "migrate"], 0, "apply 001 initial\napply 002 add_pinned\n", "")
assert rows(a) == [(1, "initial", S1), (2, "add_pinned", S2)], rows(a)
assert "decoy" not in tables(a)
expect(["--db", a, "migrate"], 0, "up to date\n", "")
expect(["--db", a, "migrate", "--dry-run"], 0, "up to date\n", "")
expect(["--db", a, "migrate", "status"], 0, "[x] 001 initial\n[x] 002 add_pinned\ncurrent: 002\n", "")
# NOTES_DB env
e = os.path.join(T, "env.db")
expect(["migrate"], 0, "apply 001 initial\napply 002 add_pinned\n", "", env=dict(ENV, NOTES_DB=e))
assert len(rows(e)) == 2

# --- B: numeric order, mixed padding, ignored files, --to
files = {"001_initial.sql": INIT_SQL}
for v, w in [(2, "two"), (3, "three"), (4, "four"), (5, "five"), (6, "six"), (7, "seven"), (8, "eight"), (9, "nine")]:
    prev = "notes" if v == 2 else f"t{v - 1}"
    files[f"{v if v % 2 else '%02d' % v}_{w}.sql"] = f"CREATE TABLE t{v} AS SELECT * FROM {prev};\n"
files["10_ten.sql"] = "CREATE TABLE t10 AS SELECT * FROM t9;\n"
files["README.md"] = "not a migration"
files["011_Bad-Name.sql"] = "THIS IS NOT SQL;"
files["12_twelve.sql.bak"] = "THIS IS NOT SQL;"
files["x_13.sql"] = "THIS IS NOT SQL;"
B = mkdir("mb", files)
b = os.path.join(T, "b.db")
expect(["--db", b, "migrate", "--dir", B, "--to", "3"], 0, "apply 001 initial\napply 002 two\napply 003 three\n", "")
expect(["--db", b, "migrate", "status", "--dir", B], 0,
       "[x] 001 initial\n[x] 002 two\n[x] 003 three\n[ ] 004 four\n[ ] 005 five\n[ ] 006 six\n[ ] 007 seven\n"
       "[ ] 008 eight\n[ ] 009 nine\n[ ] 010 ten\ncurrent: 003\n", "")
expect(["--db", b, "migrate", "--dir", B, "--to", "2"], 0, "up to date\n", "")
expect(["--db", b, "migrate", "--dir", B, "--to", "99"], 2, "", "error: unknown target version 099\n")
before = fbytes(b)
expect(["--db", b, "migrate", "--dir", B, "--dry-run", "--to", "5"], 0, "would apply 004 four\nwould apply 005 five\n", "")
assert fbytes(b) == before, "--dry-run modified the db"
expect(["--db", b, "migrate", "--dir", B], 0, "".join(f"apply {v:03d} {w}\n" for v, w in
       [(4, "four"), (5, "five"), (6, "six"), (7, "seven"), (8, "eight"), (9, "nine"), (10, "ten")]), "")
assert [r[0] for r in rows(b)] == list(range(1, 11)) and rows(b)[3][1] == "four"
assert rows(b)[9][2] == sha(os.path.join(B, "10_ten.sql"))

# --- C: validation errors (nothing changed, no file created)
c = os.path.join(T, "c.db")
D = mkdir("md", {"001_initial.sql": INIT_SQL, "002_a.sql": "CREATE TABLE a(x);", "2_b.sql": "CREATE TABLE b(x);"})
expect(["--db", c, "migrate", "--dir", D], 2, "", "error: duplicate migration version 002\n")
expect(["--db", c, "migrate", "--dir", D, "--dry-run"], 2, "", "error: duplicate migration version 002\n")
expect(["--db", c, "migrate", "status", "--dir", D], 2, "", "error: duplicate migration version 002\n")
G = mkdir("mg", {"001_initial.sql": INIT_SQL, "002_a.sql": "CREATE TABLE a(x);", "004_c.sql": "CREATE TABLE c(x);",
                 "006_e.sql": "CREATE TABLE e(x);"})
expect(["--db", c, "migrate", "--dir", G], 2, "", "error: missing migration version 003\n")
G2 = mkdir("mg2", {"002_a.sql": "CREATE TABLE a(x);", "003_b.sql": "CREATE TABLE b(x);"})
expect(["--db", c, "migrate", "--dir", G2], 2, "", "error: missing migration version 001\n")
assert not os.path.exists(c), "validation error created the db file"

# checksum mismatch / applied-not-found
K = mkdir("mk", {"001_initial.sql": INIT_SQL, "002_two.sql": "CREATE TABLE two(x);", "003_three.sql": "CREATE TABLE three(x);",
                 "004_four.sql": "CREATE TABLE four(x);", "005_five.sql": "CREATE TABLE five(x);"})
k = os.path.join(T, "k.db")
expect(["--db", k, "migrate", "--dir", K, "--to", "4"], 0, None, "")
open(os.path.join(K, "003_three.sql"), "w").write("CREATE TABLE three(x, y);")
open(os.path.join(K, "002_two.sql"), "w").write("CREATE TABLE two(x);\n-- edited\n")
before = fbytes(k)
expect(["--db", k, "migrate", "--dir", K], 3, "", "error: checksum mismatch for 002 two\n")
expect(["--db", k, "migrate", "status", "--dir", K], 3, "", "error: checksum mismatch for 002 two\n")
expect(["--db", k, "migrate", "--dir", K, "--dry-run"], 3, "", "error: checksum mismatch for 002 two\n")
assert fbytes(k) == before and "five" not in tables(k)
open(os.path.join(K, "002_two.sql"), "w").write("CREATE TABLE two(x);")
open(os.path.join(K, "003_three.sql"), "w").write("CREATE TABLE three(x);")
os.remove(os.path.join(K, "004_four.sql"))
os.remove(os.path.join(K, "005_five.sql"))
expect(["--db", k, "migrate", "--dir", K], 3, "", "error: applied migration 004 not found\n")
assert fbytes(k) == before

# --- D: failing SQL rolls back that migration only
F = mkdir("mf", {"001_initial.sql": INIT_SQL, "002_ok.sql": "CREATE TABLE ok2(x);\nINSERT INTO ok2 VALUES (1);\n",
                 "003_add_bad.sql": "CREATE TABLE bad3(x);\nINSERT INTO bad3 VALUES (1);\nINSERT INTO nosuch_table VALUES (1);\n",
                 "004_after.sql": "CREATE TABLE after4(x);\n"})
f = os.path.join(T, "f.db")
expect(["--db", f, "migrate", "--dir", F], 1, "apply 001 initial\napply 002 ok\n",
       err_prefix="error: migration 003 add_bad failed: ")
assert run("--db", f, "migrate", "--dir", F)[2].rstrip().endswith("no such table: nosuch_table"), "sqlite message missing"
assert [r[0] for r in rows(f)] == [1, 2], rows(f)
assert "bad3" not in tables(f) and "after4" not in tables(f) and "ok2" in tables(f), tables(f)
open(os.path.join(F, "003_add_bad.sql"), "w").write("CREATE TABLE bad3(x);\n")
expect(["--db", f, "migrate", "--dir", F], 0, "apply 003 add_bad\napply 004 after\n", "")

# --- E: baseline of DBs made by the old init
def old_db(p):
    con = sqlite3.connect(p)
    con.executescript(INIT_SQL)
    con.execute("INSERT INTO notes (title, body, created) VALUES ('keep me', '', '2025-12-31')")
    con.commit()
    con.close()

o = os.path.join(T, "old.db")
old_db(o)
before = fbytes(o)
expect(["--db", o, "migrate", "status"], 0, "[x] 001 initial\n[ ] 002 add_pinned\ncurrent: 001\n", "")
expect(["--db", o, "migrate", "--dry-run"], 0, "would baseline 001 initial\nwould apply 002 add_pinned\n", "")
assert fbytes(o) == before, "status/dry-run modified the old db"
expect(["--db", o, "migrate"], 0, "baseline 001 initial\napply 002 add_pinned\n", "")
assert rows(o) == [(1, "initial", S1), (2, "add_pinned", S2)], rows(o)
expect(["--db", o, "list"], 0, "   1  2025-12-31  keep me\n", "")

# --- F: init goes through migrations
i = os.path.join(T, "i.db")
expect(["--db", i, "init"], 0, f"initialized {i}\n", "")
assert rows(i) == [(1, "initial", S1), (2, "add_pinned", S2)], rows(i)
con = sqlite3.connect(i)
assert "pinned" in [x[1] for x in con.execute("PRAGMA table_info(notes)")]
con.close()
expect(["--db", i, "init"], 0, f"initialized {i}\n", "")
expect(["--db", i, "add", "hello", "--tag", "X", "--date", "2026-02-03"], 0, "added 1\n", "")
expect(["--db", i, "list"], 0, "   1  2026-02-03  hello [x]\n", "")
o3 = os.path.join(T, "old3.db")
old_db(o3)
expect(["--db", o3, "init"], 0, f"initialized {o3}\n", "")
assert rows(o3) == [(1, "initial", S1), (2, "add_pinned", S2)], rows(o3)
expect(["--db", o3, "show", "1"], 0, "   1  2025-12-31  keep me\n", "")

shutil.rmtree(T)
print(f"migrations: {N[0]} checks OK")
