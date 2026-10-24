"""Hidden check: walk all pages for many datasets/limits/authors and compare with an independent reference."""
import json, random, subprocess, sys
sys.path.insert(0, "/work")
from feed.paginate import page


def expected(posts, limit, author):
    rows = [p for p in posts if not p.get("deleted") and (author is None or p["author"] == author)]
    rows.sort(key=lambda p: (p["created_at"], p["id"]), reverse=True)
    pages = [rows[i:i + limit] for i in range(0, len(rows), limit)] or [[]]
    return [[p["id"] for p in pg] for pg in pages]


def walk(posts, limit, author):
    out, cur = [], None
    for _ in range(500):
        r = page(posts, limit, cur, author)
        out.append([p["id"] for p in r["items"]])
        cur = r["next"]
        if cur is None:
            return out
    return out + [["...no end"]]


def dataset(rng):
    n = rng.randint(0, 40)
    ids = rng.sample(range(1, 500), n)
    times = [f"2026-0{rng.randint(1, 3)}-1{rng.randint(0, 2)}T00:00:00" for _ in range(rng.randint(1, 8))]
    return [{"id": i, "created_at": rng.choice(times), "author": rng.choice("xyz"), "title": "t",
             "deleted": rng.random() < 0.25} for i in ids]


def main():
    rng = random.Random(1022)
    bad, total = [], 0
    real = [json.loads(l) for l in open("/work/data/posts.jsonl") if l.strip()]
    cases = [(real, l, a) for l in (1, 3, 5, 7, 20) for a in (None, "aki")]
    tie = [{"id": i, "created_at": "2026-01-01T00:00:00", "author": "x", "title": "t"} for i in range(1, 11)]
    cases += [(tie, 3, None), (tie, 5, None), (tie, 10, None), (tie, 4, "x")]
    for _ in range(30):
        cases.append((dataset(rng), rng.choice([1, 2, 3, 4, 5, 10]), rng.choice([None, None, "x"])))
    for posts, limit, author in cases:
        total += 1
        exp, got = expected(posts, limit, author), walk(posts, limit, author)
        if exp != got:
            bad.append(f"limit={limit} author={author} n={len(posts)}: expected pages {exp[:4]}... got {got[:4]}...")
    # CLI on the real data: page 1 lines and the next marker
    total += 1
    r = subprocess.run([sys.executable, "-m", "feed", "data/posts.jsonl", "--limit", "4", "--author", "ben"],
                       capture_output=True, text=True, cwd="/work")
    lines = r.stdout.strip().splitlines()
    exp = expected(real, 4, "ben")
    ids = [int(l.split("\t")[0]) for l in lines[:-1]]
    if r.returncode != 0 or ids != exp[0] or (lines[-1] == "next: -") != (len(exp) == 1):
        bad.append(f"CLI page 1 for ben: got {lines}, expected ids {exp[0]}")
    for b in bad[:6]:
        print(b)
    print(f"{total - len(bad)}/{total} cases ok")
    print(f"SCORE {total - len(bad)}/{total}")
    sys.exit(1 if bad else 0)


main()
