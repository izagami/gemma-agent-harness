"""Hidden check for q_csv_merge: random exports vs an independent model of docs/SPEC.md."""
import csv, io, os, random, subprocess, sys, tempfile

POOL = ["id", "name", "email", "city", "phone", "note"]
VALUES = ["", "", "Ann", "Bob", "Kyoto", "a,b", 'say "hi"', "line1\nline2", "x\r\ny", " spaced ", "東京", "0", "-"]


def variant(rng, name):
    return rng.choice([name, name.upper(), " " + name, name.title() + " ", "  " + name.upper() + "  "])


def make_file(rng, path, ids):
    cols = ["id"] + rng.sample(POOL[1:], rng.randint(1, 4))
    rng.shuffle(cols)
    header = [variant(rng, c) for c in cols]
    rows = []
    for _ in range(rng.randint(1, 6)):
        rows.append({c: (rng.choice(ids) if c == "id" and rng.random() > 0.1 else ("" if c == "id" else rng.choice(VALUES))) for c in cols})
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=rng.choice(["\n", "\r\n"]), quoting=rng.choice([csv.QUOTE_MINIMAL, csv.QUOTE_ALL]))
    w.writerow(header)
    for i, r in enumerate(rows):
        line = [r[c] for c in cols]
        if rng.random() < 0.15 and len(line) > 1:
            line = line[:-1]  # short row
        w.writerow(line)
        if rng.random() < 0.1:
            buf.write("\n")  # empty line between records
    data = buf.getvalue().encode("utf-8")
    if rng.random() < 0.5:
        data = b"\xef\xbb\xbf" + data
    with open(path, "wb") as f:
        f.write(data)
    return cols, rows


def expected(files):
    columns, order, table = [], [], {}
    for path in files:
        text = open(path, encoding="utf-8", newline="").read()
        if text.startswith("﻿"):
            text = text[1:]
        recs = [r for r in csv.reader(io.StringIO(text, newline="")) if r]
        head = [h.strip().lower() for h in recs[0]]
        for h in head:
            if h not in columns:
                columns.append(h)
        for r in recs[1:]:
            r = r + [""] * (len(head) - len(r))
            row = dict(zip(head, r))
            k = row.get("id", "")
            if k == "":
                continue
            if k not in table:
                table[k] = {}
                order.append(k)
            for c, v in row.items():
                if v != "":
                    table[k][c] = v
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(columns)
    for k in order:
        w.writerow([table[k].get(c, "") for c in columns])
    return out.getvalue(), len(order)


def main():
    rng = random.Random(20261022)
    fails = 0
    cases = 0
    tmp = tempfile.mkdtemp()
    for case in range(36):
        ids = [f"K{rng.randint(1, 6)}" for _ in range(4)]
        n = rng.choice([1, 2, 2, 3])
        files = []
        for j in range(n):
            p = os.path.join(tmp, f"c{case}_{j}.csv")
            make_file(rng, p, ids)
            files.append(p)
        out = os.path.join(tmp, f"out{case}.csv")
        r = subprocess.run([sys.executable, "-m", "csvmerge", out] + files, capture_output=True, text=True, cwd="/work")
        exp, nrows = expected(files)
        cases += 1
        got = open(out, encoding="utf-8", newline="").read() if os.path.exists(out) else None
        msg = f"merged {nrows} rows from {n} files -> {out}"
        if r.returncode != 0 or got != exp or r.stdout.strip() != msg:
            fails += 1
            if fails <= 3:
                print(f"case {case} differs (exit {r.returncode}, stdout {r.stdout.strip()!r}, stderr {r.stderr[-200:]!r})")
                print("--- expected\n" + exp + "--- got\n" + str(got))
    # the real exports from the task
    out = os.path.join(tmp, "real.csv")
    r = subprocess.run([sys.executable, "-m", "csvmerge", out, "data/crm.csv", "data/shop.csv"], capture_output=True, text=True, cwd="/work")
    exp, _ = expected(["/check/orig_crm.csv", "/check/orig_shop.csv"])
    cases += 1
    if r.returncode != 0 or open(out, encoding="utf-8", newline="").read() != exp:
        fails += 1
        print("real exports differ:\n" + exp)
    print(f"{cases - fails}/{cases} cases ok")
    sys.exit(1 if fails else 0)


main()
