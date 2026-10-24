#!/usr/bin/env python3
"""Re-run hidden checks on saved results (runs/*/TASK/work), on a copy, to verify that a changed check keeps every
pass/fail verdict and to read its graded score.

usage: regrade.py TASKS_DIR [GLOB]     e.g. regrade.py tasks_qg 'runs/v7*-1024-*'
prints per task: results, verdicts that changed, mean SCORE (from a "SCORE k/n" line, else 1/0); writes regrade.jsonl
"""
import glob, json, os, re, shutil, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import eval as E

tasks_dir = os.path.abspath(sys.argv[1]); pat = sys.argv[2] if len(sys.argv) > 2 else "runs/v7*-1024-*"
jobs = []
for f in sorted(glob.glob(os.path.join(HERE, pat, "*", "log.jsonl"))):
    d = os.path.dirname(f); t = os.path.basename(d)
    if not os.path.isdir(os.path.join(d, "work")) or not os.path.isdir(os.path.join(tasks_dir, t, "check")):
        continue
    if os.environ.get("TASKS") and t not in os.environ["TASKS"].split(","):   # only these tasks
        continue
    r = next((json.loads(l)["result"] for l in open(f) if '"result"' in l), None)
    if r is not None:
        jobs.append((t, d, bool(r["pass"])))


def score(out, ok):
    m = re.findall(r"^SCORE (\d+)/(\d+)", out, re.M)
    return int(m[-1][0]) / int(m[-1][1]) if m and int(m[-1][1]) else float(ok)


def one(j):
    t, d, was = j
    tmp = tempfile.mkdtemp(prefix="regrade-", dir=os.environ.get("REGRADE_TMP", "/tmp"))
    try:
        shutil.copytree(os.path.join(d, "work"), os.path.join(tmp, "work"), symlinks=True)
        ok, out = E.check(os.path.join(tmp, "work"), os.path.join(tasks_dir, t, "check"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return dict(task=t, run=os.path.relpath(d, HERE), was=was, now=ok, score=score(out, ok), out=out[-300:])


with ThreadPoolExecutor(int(os.environ.get("REGRADE_WORKERS", "6"))) as ex:
    res = list(ex.map(one, jobs))
with open(os.environ.get("REGRADE_OUT", os.path.join(HERE, "regrade.jsonl")), "w") as fh:
    for r in res:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
by = {}
for r in res:
    by.setdefault(r["task"], []).append(r)
for t, rs in sorted(by.items()):
    ch = [r["run"] for r in rs if r["was"] != r["now"]]
    print(f"{t:20s} n={len(rs):3d} changed={len(ch)} mean score={sum(r['score'] for r in rs) / len(rs):.2f} {ch[:3]}")
print("total", len(res), "changed", sum(r["was"] != r["now"] for r in res))
