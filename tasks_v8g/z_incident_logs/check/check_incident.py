import json, sys
exp = json.load(open("/check/truth.json"))
# tasks_v8g: one item per key of truth.json (5)
try:
    got = json.load(open("/work/incident.json"))
except Exception as e:
    print("incident.json missing or invalid:", e)
    print(f"ITEMS 0/{len(exp)}")
    sys.exit(1)
if not isinstance(got, dict):  # tasks_v8: got.get() raised (= failure)
    print("incident.json is not an object")
    print(f"ITEMS 0/{len(exp)}")
    sys.exit(1)
bad = [k for k in exp if got.get(k) != exp[k]]
for k in bad:
    g = got.get(k)
    print(f"incident.json: {k} is wrong" + (f" (got {len(g)} ids)" if isinstance(g, list) else f" (got {g!r})"))
print(f"ITEMS {len(exp) - len(bad)}/{len(exp)}")
sys.exit(1 if bad else 0)
