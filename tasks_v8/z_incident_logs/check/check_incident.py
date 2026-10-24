import json, sys
exp = json.load(open("/check/truth.json"))
try:
    got = json.load(open("/work/incident.json"))
except Exception as e:
    print("incident.json missing or invalid:", e); sys.exit(1)
bad = [k for k in exp if got.get(k) != exp[k]]
for k in bad:
    g = got.get(k)
    print(f"incident.json: {k} is wrong" + (f" (got {len(g)} ids)" if isinstance(g, list) else f" (got {g!r})"))
sys.exit(1 if bad else 0)
