"""Hidden check: random operation sequences against an independent model of docs/SPEC.md."""
import random, sys
sys.path.insert(0, "/work")
from ttlcache import FakeClock, TTLCache


class Model:
    def __init__(self, cap, ttl, clock):
        self.cap, self.ttl, self.clock = cap, ttl, clock
        self.d = {}          # key -> [value, deadline, last_use]
        self.tick = 0
        self.s = {"hits": 0, "misses": 0, "evictions": 0, "expirations": 0}

    def use(self):
        self.tick += 1
        return self.tick

    def purge(self):
        now = self.clock()
        for k in [k for k, v in self.d.items() if now >= v[1]]:
            del self.d[k]
            self.s["expirations"] += 1

    def get(self, k, default=None):
        v = self.d.get(k)
        if v is None:
            self.s["misses"] += 1
            return default
        if self.clock() >= v[1]:
            del self.d[k]
            self.s["expirations"] += 1
            self.s["misses"] += 1
            return default
        v[2] = self.use()
        self.s["hits"] += 1
        return v[0]

    def set(self, k, val, ttl=None):
        ttl = self.ttl if ttl is None else ttl
        if ttl <= 0:
            raise ValueError
        if k not in self.d and len(self.d) >= self.cap:
            self.purge()
            if len(self.d) >= self.cap:
                old = min(self.d, key=lambda x: self.d[x][2])
                del self.d[old]
                self.s["evictions"] += 1
        self.d[k] = [val, self.clock() + ttl, self.use()]

    def delete(self, k):
        return self.d.pop(k, None) is not None

    def length(self):
        self.purge()
        return len(self.d)

    def contains(self, k):
        v = self.d.get(k)
        return v is not None and self.clock() < v[1]


def run(seed):
    rng = random.Random(seed)
    cap, ttl = rng.randint(1, 5), rng.choice([3, 5, 10])
    ca, cb = FakeClock(), FakeClock()
    real, ref = TTLCache(cap, ttl, clock=ca), Model(cap, ttl, cb)
    keys = "abcdefg"[: rng.randint(2, 7)]
    for step in range(60):
        op = rng.random()
        k = rng.choice(keys)
        if op < 0.35:
            t = rng.choice([None, None, rng.randint(1, 8)])
            out = (real.set(k, step, t), ref.set(k, step, t))
            name = f"set({k!r}, {step}, ttl={t})"
        elif op < 0.7:
            out = (real.get(k, "-"), ref.get(k, "-"))
            name = f"get({k!r})"
        elif op < 0.75:
            out = (real.delete(k), ref.delete(k))
            name = f"delete({k!r})"
        elif op < 0.82:
            out = (len(real), ref.length())
            name = "len()"
        elif op < 0.88:
            out = (k in real, ref.contains(k))
            name = f"{k!r} in cache"
        else:
            dt = rng.choice([1, 1, 2, ttl - 1, ttl, rng.randint(1, 12)])
            ca.advance(dt); cb.advance(dt)
            continue
        if out[0] != out[1] or real.stats() != ref.s:
            return f"seed {seed} cap={cap} ttl={ttl} step {step} t={ca()} {name}: got {out[0]!r} stats {real.stats()}, expected {out[1]!r} stats {ref.s}"
    return None


def fixed():
    c = FakeClock()
    x = TTLCache(2, 10, clock=c)
    x.set("a", 1)
    c.advance(10)
    yield "expired exactly at t+ttl", x.get("a") is None
    c2 = FakeClock(); y = TTLCache(2, 10, clock=c2)
    y.set("a", 1); c2.advance(6); y.get("a"); c2.advance(6)
    yield "get does not extend life", y.get("a") is None
    c3 = FakeClock(); z = TTLCache(2, 10, clock=c3)
    z.set("a", 1, ttl=2); z.set("b", 2); c3.advance(3); z.set("c", 3)
    yield "expired removed before LRU eviction", ("b" in z) and z.stats()["evictions"] == 0 and z.stats()["expirations"] == 1
    c4 = FakeClock(); w = TTLCache(2, 10, clock=c4)
    w.set("a", 1); w.set("b", 2); w.set("a", 3)
    yield "replacing a key never evicts", ("b" in w) and w.get("a") == 3 and w.stats()["evictions"] == 0


def main():
    bad = []
    for name, ok in fixed():
        if not ok:
            bad.append("fixed: " + name)
    for seed in range(40):
        r = run(seed)
        if r:
            bad.append(r)
    total = 44
    for b in bad[:6]:
        print(b)
    print(f"{total - len(bad)}/{total} cases ok")
    print(f"SCORE {total - len(bad)}/{total}")
    sys.exit(1 if bad else 0)


main()
