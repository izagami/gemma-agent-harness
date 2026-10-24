"""Hidden check for z_price_cache: tier changes / price reloads with a warm cache; the cache must stay."""
import json, os, subprocess, sys
sys.path.insert(0, "/work")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
from shop.service import Service

TIER = {"standard": 0, "silver": 5, "gold": 10, "platinum": 15}


def expect(price, tier, cat):
    pct = TIER[tier]
    if cat == "sale":
        pct //= 2
    elif cat == "bulk" and tier in ("gold", "platinum"):
        pct += 3
    pct = min(pct, 20)
    return (price * (100 - pct) + 50) // 100


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


D2 = "/check/data2"
cat = {p["sku"]: p for p in load(f"{D2}/catalog.json")}
s = Service.from_dir(D2)
P = s.pricing
tiers = {c["id"]: c["tier"] for c in load(f"{D2}/customers.json")}


def verify(cid, sku):
    got = P.unit_price(cid, sku)
    want = expect(cat[sku]["price"], tiers[cid], cat[sku]["category"])
    assert got == want, (cid, sku, tiers[cid], got, want)


def hits():
    return P.stats()["hits"]


# warm every pair
for cid in tiers:
    for sku in cat:
        verify(cid, sku)
h = hits()
verify("K02", "A2")
assert hits() == h + 1, "an identical lookup right after another must be a cache hit"

steps = [("tier", "K02", "gold"), ("tier", "K04", "standard"), ("reload", "prices_b.json"), ("tier", "K02", "silver"),
         ("tier", "K05", "platinum"), ("reload", "prices_c.json"), ("tier", "K02", "standard"), ("tier", "K03", "silver")]
for st in steps:
    if st[0] == "tier":
        s.customers.set_tier(st[1], st[2])
        tiers[st[1]] = st[2]
    else:
        s.catalog.reload(load(f"{D2}/{st[1]}"))
        cat = {p["sku"]: p for p in load(f"{D2}/{st[1]}")}
    for cid in sorted(tiers):
        for sku in cat:
            verify(cid, sku)
    # nothing changed since the sweep above: a second sweep is served from the cache
    h = hits()
    for cid in sorted(tiers):
        for sku in cat:
            verify(cid, sku)
    assert hits() == h + len(tiers) * len(cat), (st, "second sweep was not cached", hits() - h)

# a separate service instance is not affected by the first one
s2 = Service.from_dir(D2)
assert s2.pricing.unit_price("K02", "A2") == expect(6200, "standard", "bulk")

# scenario replays (golden output from the reference behaviour)
env = dict(os.environ, PYTHONPATH="/work")
for data, scen, exp in [("/work/data", "/work/data/may01.jsonl", "/check/exp_may01.txt"),
                        (D2, f"{D2}/week.jsonl", "/check/exp_week.txt")]:
    r = subprocess.run([sys.executable, "-m", "shop", "replay", data, scen], cwd="/tmp", env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    want = open(exp, encoding="utf-8").read()
    assert r.stdout == want, (scen, r.stdout, want)
print("ok")
