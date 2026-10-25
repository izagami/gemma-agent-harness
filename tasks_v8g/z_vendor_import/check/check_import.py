"""Hidden check for z_vendor_import: fresh vendor files, chunk-boundary splits, BOMs, cp932, idempotency."""
import sys; sys.dont_write_bytecode = True
import csv, io, json, os, re, subprocess, sys
sys.path.insert(0, "/check")
from people import people

D = "/tmp/vi"
os.makedirs(D, exist_ok=True)
STORE = os.path.join(D, "store.json")
if os.path.exists(STORE):
    os.remove(STORE)
P = people(160, 42, "q")
FW = str.maketrans("0123456789-", "０１２３４５６７８９－")


def csvtext(header, rows):
    b = io.StringIO(); w = csv.writer(b, lineterminator="\r\n"); w.writerow(header); w.writerows(rows); return b.getvalue()


PADDED = set()  # people whose name in a generated file carries filler so that characters straddle probe offsets


def make_utf8(header, rows, bom, offsets, allowed):
    """rows: list of (person index, row tuple with the name at column 1).  Appends filler to the names of some
    rows in `allowed` (greedy, left to right) until a multi-byte UTF-8 character straddles every offset."""
    pads = {}

    def build():
        out = [list(r) for _, r in rows]
        for k, v in pads.items():
            out[k][1] = out[k][1] + v
        data = csvtext(header, out).encode("utf-8")
        return (b"\xef\xbb\xbf" + data) if bom else data

    for o in offsets:
        prev = build()
        # a row that starts after the previous offsets: padding it does not move them
        lo = max([x for x in offsets if x < o], default=0)
        cand = [k for k, (i, _) in enumerate(rows) if i in allowed and len(build_prefix(header, rows, pads, k, bom)) > lo + 2
                and len(build_prefix(header, rows, pads, k + 1, bom)) < o]
        assert cand, ("no row to pad before", o)
        k = cand[0]
        for t in range(200):
            pads[k] = "様" * (t % 5) + "." * (t // 5)
            d = build()
            if len(d) > o and (d[o] & 0xC0) == 0x80:
                PADDED.add(rows[k][0])
                break
        else:
            raise SystemExit("generator: could not place split")
    d = build()
    for o in offsets:
        assert (d[o] & 0xC0) == 0x80
    return d


def build_prefix(header, rows, pads, k, bom):
    out = [list(r) for _, r in rows[:k]]
    for j, v in pads.items():
        if j < k:
            out[j][1] = out[j][1] + v
    data = csvtext(header, out).encode("utf-8")
    return (b"\xef\xbb\xbf" + data) if bom else data


files = []
# 1. cp932, Japanese headers in a new order
rows = [(n.replace(" ", "　") if i % 2 else n, p.translate(FW) if i % 3 == 0 else p, e, f"X{i:05d}")
        for i, (n, e, p) in enumerate(P[:40])]
open(f"{D}/shop_x.csv", "wb").write(csvtext(["顧客名", "電話", "メール", "顧客ID"], rows).encode("cp932"))
files.append("shop_x")
# 2. UTF-8 + BOM, e-mail first, big, split multibyte characters at 1024/2048/3000
rows = [(i, (e.upper() if i % 4 == 0 else e, n, p, f"Y-{i}")) for i, (n, e, p) in enumerate(P[30:90], start=30)]
open(f"{D}/shop_y.csv", "wb").write(make_utf8(["mail", "name", "phone", "id"], rows, True, [1024, 2048, 3000], range(40, 85)))
files.append("shop_y")
# 3. UTF-8 without BOM, no e-mail column (merges by name+phone), split at the probe boundaries
rows = [(i, (f"Z{i}", n, p)) for i, (n, e, p) in enumerate(P[85:160], start=85)]
open(f"{D}/shop_z.csv", "wb").write(make_utf8(["customer_no", "full_name", "tel"], rows, False, [1024, 2048], range(90, 160)))
files.append("shop_z")
# 4. tiny UTF-8 + BOM file whose first column is the id
rows = [(f"W{i}", n, e) for i, (n, e, p) in enumerate(P[:3])]
open(f"{D}/shop_w.csv", "wb").write(b"\xef\xbb\xbf" + csvtext(["id", "氏名", "email"], rows).encode("utf-8"))
files.append("shop_w")

# expected ledger, derived from the people list (sources in import order)
exp = {}
def src(i, s):
    exp.setdefault(i, {"name": P[i][0], "sources": []})["sources"].append(s)
for i in range(40): src(i, f"shop_x:X{i:05d}")
for i in range(30, 90): src(i, f"shop_y:Y-{i}")
for i in range(85, 160): src(i, f"shop_z:Z{i}")
for i in range(3): src(i, f"shop_w:W{i}")

env = dict(os.environ, PYTHONPATH="/work", PYTHONDONTWRITEBYTECODE="1")


def run(*a):
    r = subprocess.run([sys.executable, "-m", "custimport", *a], cwd=D, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, (a, r.stdout, r.stderr[-800:])
    return r.stdout


# tasks_v8g items (11): first import counts, store size, ledger (sources + names), per-customer checks (no U+FFFD,
# no BOM, e-mail shape), shop_z-only e-mails empty, Y-50 e-mail, re-import counts, store unchanged by re-import, seed
# import. All run even after a failure (tasks_v8 stopped at the first one); the verdict is the same.
ITEMS = [0, 0]
FAILS = []
G = {}


def item(fn):
    ITEMS[1] += 1
    try:
        fn()
        ITEMS[0] += 1
    except Exception as x:  # noqa: BLE001
        FAILS.append(f"{fn.__name__}: {x!r}"[:600])


def first_import():
    G["out"] = run("import", STORE, *[f"{D}/{f}.csv" for f in files])
    counts = {m.group(1): tuple(map(int, m.groups()[1:])) for m in re.finditer(r"^(\w+): .*?added=(\d+) merged=(\d+) skipped=(\d+)", G["out"], re.M)}
    assert counts == {"shop_x": (40, 0, 0), "shop_y": (50, 10, 0), "shop_z": (70, 5, 0), "shop_w": (0, 3, 0)}, (counts, G["out"])


def store_size():
    d = json.load(open(STORE, encoding="utf-8"))
    G["cs"] = cs = d["customers"]
    G["by_src"] = {s: c for c in cs for s in c["sources"]}
    assert len(cs) == 160 and d["next_id"] == 161, (len(cs), d["next_id"])


def ledger():
    by_src = G["by_src"]
    bad = []
    for i, e in exp.items():
        c = by_src.get(e["sources"][0])
        if c is None or c["sources"] != e["sources"]:
            bad.append((i, e["sources"], c and c["sources"]))
            continue
        # the name is the first source's spelling (whitespace cleaned); some rows carry generator filler
        if not (c["name"] == P[i][0] or (i in PADDED and c["name"].startswith(P[i][0]))):
            bad.append((i, "name", c["name"], P[i][0]))
    assert not bad, bad[:5]


def no_replacement_char():
    for c in G["cs"]:
        assert "\ufffd" not in json.dumps(c, ensure_ascii=False), c


def no_bom():
    for c in G["cs"]:
        assert not any("\ufeff" in str(v) for v in c.values()), c


def email_shape():
    for c in G["cs"]:
        assert c["email"] == "" or re.fullmatch(r"[A-Za-z0-9.]+@[A-Za-z.]+", c["email"]), c


# e-mail for customers only seen in shop_z stays empty; others have one
def shop_z_emails_empty():
    assert all(G["by_src"][f"shop_z:Z{i}"]["email"] == "" for i in range(90, 160))


def y50_email():
    assert G["by_src"]["shop_y:Y-50"]["email"] == P[50][1]


def reimport_counts():
    G["before"] = open(STORE, "rb").read()
    out2 = run("import", STORE, *[f"{D}/{f}.csv" for f in files])
    counts2 = {m.group(1): tuple(map(int, m.groups()[1:])) for m in re.finditer(r"^(\w+): .*?added=(\d+) merged=(\d+) skipped=(\d+)", out2, re.M)}
    assert counts2 == {"shop_x": (0, 0, 40), "shop_y": (0, 0, 60), "shop_z": (0, 0, 75), "shop_w": (0, 0, 3)}, counts2


def reimport_unchanged():
    assert open(STORE, "rb").read() == G["before"], "re-import changed the store"


# the seed vendor files still import correctly
def seed_import():
    S2 = os.path.join(D, "seed.json")
    if os.path.exists(S2):
        os.remove(S2)
    out3 = run("import", S2, "/work/data/vendor_a.csv", "/work/data/vendor_b.csv", "/work/data/vendor_c.csv")
    d = json.load(open(S2, encoding="utf-8"))
    assert len(d["customers"]) == 75, (len(d["customers"]), out3)


for fn in (first_import, store_size, ledger, no_replacement_char, no_bom, email_shape, shop_z_emails_empty, y50_email,
           reimport_counts, reimport_unchanged, seed_import):
    item(fn)
for f in FAILS[:3]:
    print("FAIL", f)
print("ok" if not FAILS else f"{len(FAILS)} failed")
print(f"ITEMS {ITEMS[0]}/{ITEMS[1]}")
sys.exit(1 if FAILS else 0)
