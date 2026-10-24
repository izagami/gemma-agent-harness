"""Hidden check: compare the CLI with an independent reference on fixed and random dependency files."""
import os, random, subprocess, sys, tempfile


def ref_parse(text):
    deps = {}
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        t, rest = line.split(":", 1)
        t = t.strip()
        deps.setdefault(t, set())
        for d in rest.split():
            deps.setdefault(d, set())
            deps[t].add(d)
    return deps


def ref_run(text, targets):
    deps = ref_parse(text)
    for t in targets:
        if t not in deps:
            return 1, "", f"error: unknown target {t}\n"
    if targets:
        keep, todo = set(), list(targets)
        while todo:
            n = todo.pop()
            if n not in keep:
                keep.add(n)
                todo += deps[n]
    else:
        keep = set(deps)
    done, order = set(), []
    while True:
        avail = [n for n in keep if n not in done and all(d in done for d in deps[n])]
        if not avail:
            break
        n = min(avail)
        done.add(n)
        order.append(n)
    if len(order) < len(keep):
        left = keep - done
        n, walk = min(left), []
        while n not in walk:
            walk.append(n)
            n = min(d for d in deps[n] if d in left)
        cyc = walk[walk.index(n):] + [n]
        return 2, "", "error: cycle: " + " -> ".join(cyc) + "\n"
    return 0, "".join(n + "\n" for n in order), ""


FIXED = [
    ("app: lib util\nlib: base\nutil: base\n", []),
    ("a: b\nb: c\nc: d\nd: b\n", []),
    ("x: x\n", []),
    ("a: b b b\nb:\n", []),
    ("a: b\na: c b\nc:\n", []),
    ("z: a\ny: a\nx: a\nm: z\nb: y\n", []),
    ("top: mid\nmid: low\nlow:\nother: low\n", ["top"]),
    ("top: mid\nmid: low\nlow: deep\ndeep:\nother:\n", ["top"]),
    ("a: b\nb: a\nc:\n", ["c"]),
    ("a: b\nb: a\nc: a\n", ["c"]),
    ("q: w e\nw: e\ne:\n", ["nope"]),
    ("b: c\nc: b\na: a2\na2: a\n", []),
]


def rand_case(rng):
    names = rng.sample(["ab", "ac", "b", "ba", "c", "core", "d", "e", "lib", "m", "n", "net", "ui", "x", "y", "z"], rng.randint(4, 12))
    order = names[:]
    rng.shuffle(order)
    lines = []
    for i, t in enumerate(order):
        cand = order[i + 1:]
        ds = [rng.choice(cand) for _ in range(rng.randint(0, 3))] if cand else []
        if rng.random() < 0.3 and ds:
            ds.append(ds[0])
        lines.append(f"{t}: {' '.join(ds)}")
        if rng.random() < 0.2 and cand:
            lines.append(f"{t}: {rng.choice(cand)}  # more")
    cyc = rng.random() < 0.35
    if cyc and len(order) > 2:
        i = rng.randrange(1, len(order))
        j = rng.randrange(0, i)
        lines.append(f"{order[i]}: {order[j]}")
    rng.shuffle(lines)
    targets = rng.sample(names, rng.randint(1, 2)) if rng.random() < 0.4 else []
    return "\n".join(lines) + "\n", targets


def main():
    rng = random.Random(20261022)
    cases = FIXED + [rand_case(rng) for _ in range(40)]
    cases.append((open("/work/data/project.deps").read(), []))
    cases.append((open("/work/data/project.deps").read(), ["tls", "widgets"]))
    d = tempfile.mkdtemp()
    bad = 0
    for k, (text, targets) in enumerate(cases):
        p = os.path.join(d, f"c{k}.deps")
        open(p, "w").write(text)
        r = subprocess.run([sys.executable, "-m", "buildorder", p, *targets], capture_output=True, text=True, cwd="/work")
        exp = ref_run(text, targets)
        got = (r.returncode, r.stdout, r.stderr)
        if got != exp:
            bad += 1
            if bad <= 5:
                print(f"case {k} targets={targets}\n{text}--- expected {exp!r}\n--- got {got!r}")
    print(f"{len(cases) - bad}/{len(cases)} cases ok")
    print(f"SCORE {len(cases) - bad}/{len(cases)}")
    sys.exit(1 if bad else 0)


main()
