"""Hidden check for z_price_cache: tier changes / price reloads with a warm cache; the cache must stay."""
import json, os, subprocess, sys
sys.path.insert(0, "/work")
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
try:
    from shop.service import Service
except Exception as x:  # noqa: BLE001 - tasks_v8: ended the script (= failure); here only the in-process items fail
    print("import shop.service failed:", repr(x)[:300])
    Service = None

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
try:
    s = Service.from_dir(D2)
    P = s.pricing
except Exception as x:  # noqa: BLE001
    print("Service.from_dir failed:", repr(x)[:300])
    s = P = None
tiers = {c["id"]: c["tier"] for c in load(f"{D2}/customers.json")}


def verify(cid, sku):
    got = P.unit_price(cid, sku)
    want = expect(cat[sku]["price"], tiers[cid], cat[sku]["category"])
    assert got == want, (cid, sku, tiers[cid], got, want)


def hits():
    return P.stats()["hits"]


# tasks_v8g items (21): warm sweep, repeated lookup is a hit, per step (8) "sweep correct" + "second sweep cached",
# separate instance, 2 scenario replays. Every item runs even after a failure (tasks_v8 stopped at the first one).
ITEMS = [0, 0]
FAILS = []


def item(fn):
    ITEMS[1] += 1
    try:
        if s is None:
            raise AssertionError("no Service")
        fn()
        ITEMS[0] += 1
    except Exception as x:  # noqa: BLE001
        FAILS.append(f"{fn.__name__}: {x!r}"[:600])


# warm every pair
def warm_sweep():
    for cid in tiers:
        for sku in cat:
            verify(cid, sku)


item(warm_sweep)


def repeat_is_hit():
    h = hits()
    verify("K02", "A2")
    assert hits() == h + 1, "an identical lookup right after another must be a cache hit"


item(repeat_is_hit)

steps = [("tier", "K02", "gold"), ("tier", "K04", "standard"), ("reload", "prices_b.json"), ("tier", "K02", "silver"),
         ("tier", "K05", "platinum"), ("reload", "prices_c.json"), ("tier", "K02", "standard"), ("tier", "K03", "silver")]
for st in steps:
    def sweep_after_change():
        global cat
        if st[0] == "tier":
            tiers[st[1]] = st[2]
            s.customers.set_tier(st[1], st[2])
        else:
            cat = {p["sku"]: p for p in load(f"{D2}/{st[1]}")}
            s.catalog.reload(load(f"{D2}/{st[1]}"))
        for cid in sorted(tiers):
            for sku in cat:
                verify(cid, sku)
    sweep_after_change.__name__ = f"sweep after {st}"
    item(sweep_after_change)

    # nothing changed since the sweep above: a second sweep is served from the cache
    def second_sweep_cached():
        h = hits()
        for cid in sorted(tiers):
            for sku in cat:
                verify(cid, sku)
        assert hits() == h + len(tiers) * len(cat), (st, "second sweep was not cached", hits() - h)
    second_sweep_cached.__name__ = f"cached sweep after {st}"
    item(second_sweep_cached)


# a separate service instance is not affected by the first one
def separate_instance():
    s2 = Service.from_dir(D2)
    assert s2.pricing.unit_price("K02", "A2") == expect(6200, "standard", "bulk")


item(separate_instance)

# scenario replays (golden output from the reference behaviour)
env = dict(os.environ, PYTHONPATH="/work")
for data, scen, exp in [("/work/data", "/work/data/may01.jsonl", "/check/exp_may01.txt"),
                        (D2, f"{D2}/week.jsonl", "/check/exp_week.txt")]:
    def replay():
        r = subprocess.run([sys.executable, "-m", "shop", "replay", data, scen], cwd="/tmp", env=env,
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0, r.stderr[-800:]
        want = open(exp, encoding="utf-8").read()
        assert r.stdout == want, (scen, r.stdout[:300], want[:300])
    replay.__name__ = f"replay {os.path.basename(scen)}"
    ITEMS[1] += 1  # replays do not need the in-process Service
    try:
        replay()
        ITEMS[0] += 1
    except Exception as x:  # noqa: BLE001
        FAILS.append(f"{replay.__name__}: {x!r}"[:600])
for f in FAILS[:4]:
    print("FAIL", f)
print("ok" if not FAILS else f"{len(FAILS)} failed")
print(f"ITEMS {ITEMS[0]}/{ITEMS[1]}")
sys.exit(1 if FAILS else 0)
