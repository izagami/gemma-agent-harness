#!/usr/bin/env python3
"""Paired graded-score comparison of the variants in a regrade.jsonl (regrade.py output), variant = profile + logged env.
usage: score_cmp.py REGRADE_JSONL"""
import json, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__))
R = [json.loads(l) for l in open(sys.argv[1])]
V = collections.defaultdict(dict)
for r in R:
    log = os.path.join(HERE, r["run"], "log.jsonl")
    h = next((json.loads(l) for l in open(log) if '"feats"' in l), {})
    env = {k: v for k, v in (h.get("env") or {}).items() if not k.startswith("EV_")}
    var = h.get("profile", "?") + (":" + ",".join(f"{k}={v}" for k, v in sorted(env.items())) if env else "")
    V[var][r["task"]] = r
names = sorted(V)
for v in names:
    rs = V[v].values()
    print(f"{v}: n={len(rs)} pass={sum(r['now'] for r in rs)} mean score={sum(r['score'] for r in rs) / len(rs):.3f}")
for i, a in enumerate(names):
    for b in names[i + 1:]:
        common = sorted(set(V[a]) & set(V[b]))
        d = [V[b][t]["score"] - V[a][t]["score"] for t in common]
        if d:
            print(f"{b}  minus  {a}: {sum(d) / len(d):+.3f} over {len(d)} tasks (better {sum(x > 0.001 for x in d)}, worse {sum(x < -0.001 for x in d)})")
            print("   per task:", {t: round(x, 2) for t, x in zip(common, d)})
