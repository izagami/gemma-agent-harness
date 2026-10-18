#!/usr/bin/env python3
"""Run one profile over the task suite on several model servers at once (one task per server at a time).

usage: evalmulti.py PROFILE [task ...]   servers: LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
Writes runs/<profile>-<time>/ like eval.py (results.jsonl has every task) and prints a summary by tier.
"""
import json, os, queue, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.environ.get("LANES", "http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087").split(",")


def tier(t):
    return {"h": "hard", "x": "multi-file", "y": "repo-scale"}.get(t.split("_")[0], "easy") if "_" in t and t[1] == "_" else "easy"


def main():
    prof, tasks = sys.argv[1], sys.argv[2:] or sorted(os.listdir(os.path.join(HERE, "tasks")))
    # longest tasks first so the lanes finish together
    order = sorted(tasks, key=lambda t: {"repo-scale": 0, "multi-file": 1, "hard": 2, "easy": 3}[tier(t)])
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

    th = [threading.Thread(target=lane, args=(u,)) for u in LANES]
    [x.start() for x in th]; [x.join() for x in th]
    rs = [json.loads(l) for l in open(os.path.join(run, "results.jsonl"))]
    by = {}
    for r in rs:
        by.setdefault(tier(r["task"]), []).append(r["pass"])
    parts = " ".join(f"{k} {sum(v)}/{len(v)}" for k, v in sorted(by.items()))
    print(f"== {prof}: {sum(r['pass'] for r in rs)}/{len(rs)} passed in {round(time.time() - t0)} s  [{parts}]  ({run})", flush=True)


if __name__ == "__main__":
    main()
