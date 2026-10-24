#!/usr/bin/env python3
"""Run one profile over the task suite on several model servers at once (PER_LANE tasks per server at a time, default 1).

usage: evalmulti.py PROFILE [task ...]   servers: LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
Writes runs/<profile>-<time>/ like eval.py (results.jsonl has every task) and prints a summary by tier.
"""
import json, os, queue, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.environ.get("TASKS_DIR", os.path.join(HERE, "tasks"))
LANES = os.environ.get("LANES", "http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087").split(",")


def tier(t):
    if t.startswith("cad_"):
        return "cad"
    return {"h": "hard", "x": "multi-file", "y": "repo-scale", "z": "v8"}.get(t.split("_")[0], "easy") if "_" in t and t[1] == "_" else "easy"


def main():
    prof, tasks = sys.argv[1], sys.argv[2:] or sorted(os.listdir(TASKS_DIR))
    # longest tasks first so the lanes finish together: by the longest time each task took in earlier runs of
    # this suite (q25 10-23: alphabetical order left the slow vba_* tasks for last, ~1 lane busy at the end)
    past = {}
    for f in __import__("glob").glob(os.path.join(HERE, "runs", "*", "results.jsonl")):
        try:
            for l in open(f):
                r = json.loads(l)
                if r.get("task") in tasks and r.get("seconds"):
                    past[r["task"]] = max(past.get(r["task"], 0), r["seconds"])
        except (OSError, ValueError):
            pass
    order = sorted(tasks, key=lambda t: ({"v8": 0, "repo-scale": 0, "multi-file": 1, "hard": 2, "cad": 2, "easy": 3}[tier(t)]
                                         if not past else 0, -past.get(t, 1e9)))
    q = queue.Queue(); [q.put(t) for t in order]
    stamp = time.strftime("%m%d-%H%M%S")
    run = os.path.join(HERE, "runs", f"{prof}-{stamp}")
    os.makedirs(run)
    lock = threading.Lock()
    t0 = time.time()

    def lane(url):
        env = dict(os.environ, AGENT_API=url.rstrip("/") + "/v1/chat/completions")
        while True:
            try:
                t = q.get_nowait()
            except queue.Empty:
                return
            # eval.py in a subprocess: module-level API settings stay per lane
            r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "eval.py"), prof, t], env=env, capture_output=True, text=True)
            sub = [l for l in r.stdout.splitlines() if l.startswith("== ")]
            d = sub[-1].rsplit("(", 1)[-1].rstrip(")") if sub else None
            with lock:
                if d and os.path.exists(os.path.join(d, "results.jsonl")):
                    res = json.loads(open(os.path.join(d, "results.jsonl")).read().splitlines()[0])
                    os.rename(os.path.join(d, t), os.path.join(run, t))
                    os.rmdir(d) if not os.listdir(d) else None
                    res["lane"] = url
                    open(os.path.join(run, "results.jsonl"), "a").write(json.dumps(res, ensure_ascii=False) + "\n")
                    print(f"{t:16s} {'PASS' if res['pass'] else 'fail'} steps={res.get('steps')} t={res.get('seconds')} {res.get('error', '')}", flush=True)
                else:
                    print(f"{t:16s} ERROR {r.stderr[-300:]}", flush=True)

    # PER_LANE tasks at once on each server (llama-server -np 2 has 2 slots; one task each left half of them idle)
    th = [threading.Thread(target=lane, args=(u,)) for u in LANES for _ in range(int(os.environ.get("PER_LANE", "1")))]
    [x.start() for x in th]; [x.join() for x in th]
    rs = [json.loads(l) for l in open(os.path.join(run, "results.jsonl"))]
    by = {}
    for r in rs:
        by.setdefault(tier(r["task"]), []).append(r["pass"])
    parts = " ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by.items()))
    print(f"== {prof}: {sum(r['pass'] for r in rs)}/{len(rs)} passed in {round(time.time() - t0)} s  [{parts}]  ({run})", flush=True)


if __name__ == "__main__":
    main()
