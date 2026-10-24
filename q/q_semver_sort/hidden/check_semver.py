"""Hidden check for q_semver_sort: an independent SemVer 2.0.0 reference."""
import os, random, re, subprocess, sys, tempfile
sys.path.insert(0, "/work")
from vsort.compare import compare
from vsort.parse import InvalidVersion, parse

RX = re.compile(r"^[vV]?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
                r"(?:-((?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(?:\.(?:0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
                r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$")


def ok(s):
    return RX.match(s.strip()) is not None


def rcmp(a, b):
    ma, mb = RX.match(a.strip()), RX.match(b.strip())
    ca = [int(x) for x in ma.group(1, 2, 3)]; cb = [int(x) for x in mb.group(1, 2, 3)]
    if ca != cb:
        return -1 if ca < cb else 1
    pa, pb = ma.group(4), mb.group(4)
    if pa is None or pb is None:
        return 0 if pa == pb else (1 if pa is None else -1)
    xa, xb = pa.split("."), pb.split(".")
    for i, j in zip(xa, xb):
        if i == j:
            continue
        di, dj = i.isdigit(), j.isdigit()
        if di and dj:
            return -1 if int(i) < int(j) else 1
        if di != dj:
            return -1 if di else 1
        return -1 if i < j else 1
    return (len(xa) > len(xb)) - (len(xa) < len(xb))


valid = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11",
         "1.0.0-rc.1", "1.0.0", "1.0.0+exp.sha-5114f85", "v1.0.0+20130313144700", "1.0.0-1", "1.0.0-0",
         "1.0.0--x", "1.0.0-x-y.2", "1.0.0-rc.1+build-1.0", "2.0.0", "1.10.0", "1.9.0", "0.0.0", "10.0.0-a.b.c.10",
         "10.0.0-a.b.c.9", "10.0.0-a.b.c", "1.0.0-0A", "1.0.0-A", "1.0.0-a", "V3.2.1-rc.10", "3.2.1-rc.2+x-y-z"]
invalid = ["01.0.0", "1.02.0", "1.0.00", "1.0.0-rc.01", "1.0.0-", "1.0.0+", "1.0.0-rc..1", "1.0", "1.0.0-r$",
           "1.0.0+a..b", "x1.0.0", "1.0.0-00"]
bad = []
for s in valid:
    try:
        parse(s)
    except InvalidVersion as e:
        bad.append(f"parse({s!r}) raised {e}")
for s in invalid:
    try:
        parse(s)
        bad.append(f"parse({s!r}) accepted an invalid version")
    except InvalidVersion:
        pass
pairs = [(a, b) for a in valid for b in valid]
for a, b in pairs:
    if bad and len(bad) > 12:
        break
    try:
        got = compare(a, b)
    except Exception as e:
        bad.append(f"compare({a!r}, {b!r}) raised {e!r}"); continue
    if got != rcmp(a, b):
        bad.append(f"compare({a!r}, {b!r}) = {got}, want {rcmp(a, b)}")
if bad:
    print(f"{len(bad)} problems:"); print("\n".join(bad[:10])); sys.exit(1)


def run(*args):
    r = subprocess.run([sys.executable, "-m", "vsort", *args], cwd="/work", capture_output=True, text=True)
    return r.returncode, r.stdout.splitlines(), r.stderr.splitlines()


import functools
rng = random.Random(7)
for trial in range(4):
    lines = rng.sample(valid, len(valid)) + rng.sample(invalid, 3) + ["# comment", ""]
    rng.shuffle(lines)
    d = tempfile.mkdtemp()
    p = os.path.join(d, "v.txt")
    open(p, "w").write("\n".join(lines) + "\n")
    good = [l for l in lines if l.strip() and not l.startswith("#") and ok(l)]
    want = sorted(good, key=functools.cmp_to_key(rcmp))
    want_desc = sorted(good, key=functools.cmp_to_key(lambda a, b: -rcmp(a, b)))
    code, out, err = run("sort", p)
    assert out == want, f"sort:\n got {out}\nwant {want}"
    assert code == 1 and sorted(err) == sorted(f"invalid version: {l.strip()}" for l in lines if l.strip() and not l.startswith("#") and not ok(l)), (code, err)
    code, out, err = run("sort", "--desc", p)
    assert out == want_desc, f"sort --desc:\n got {out}\nwant {want_desc}"
    best = good[0]
    for v in good[1:]:
        if rcmp(v, best) > 0:
            best = v
    code, out, err = run("max", p)
    assert out == [best], f"max: got {out} want {best}"
code, out, err = run("max", "/work/data/releases.txt")
assert (code, out) == (0, ["2.0.0-alpha.1"]), (code, out, err)
d = tempfile.mkdtemp(); p = os.path.join(d, "tie.txt")
open(p, "w").write("1.1.9\n1.2.0+b.2\nv1.2.0\n1.2.0+a\n1.2.0-rc.9\n")
code, out, err = run("max", p)
assert (code, out) == (0, ["1.2.0+b.2"]), ("max with equal versions", code, out, err)
code, out, err = run("sort", "--desc", p)
assert out == ["1.2.0+b.2", "v1.2.0", "1.2.0+a", "1.2.0-rc.9", "1.1.9"], ("sort --desc with equal versions", out)
code, out, err = run("sort", "/work/data/releases.txt")
assert code == 0 and out == ["v1.3.2", "1.3.10", "1.4.0-beta", "1.4.0-rc.1", "1.4.0-rc.2", "1.4.0-rc.10", "1.4.0",
                             "1.4.0+build-7", "2.0.0-alpha.1"], (code, out, err)
for a, b, w in [("1.0.0-rc.2", "1.0.0-rc.10", "<"), ("1.0.0+a", "1.0.0+b", "="), ("1.0.0-alpha", "1.0.0-1", ">")]:
    assert run("cmp", a, b)[1] == [w], (a, b)
code, out, err = run("cmp", "1.0.0", "01.0.0")
assert code == 1 and err and err[0].startswith("error:"), (code, out, err)
print(f"ok: {len(pairs)} comparisons, {len(valid) + len(invalid)} parses, CLI")
