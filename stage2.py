#!/usr/bin/env python3
"""Stage 2 of the fast loop: continue saved runs from their first finish call with another profile.
usage: stage2.py PROFILE CKPT_DIR BASE_RUN_DIR [task ...]
BASE_RUN_DIR holds the original results (pass/fail of the saved runs). Prints both verdicts per task."""
import glob, json, os, queue, subprocess, sys, threading

HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.environ.get("LANES", "http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087").split(",")


def main():
    prof, ck, base = sys.argv[1:4]
    want = sys.argv[4:]
    orig = {}
    for f in glob.glob(os.path.join(base + "*", "results.jsonl")):
        for l in open(f):
            d = json.loads(l); orig[d["task"]] = d["pass"]
    tasks = [t for t in sorted(os.listdir(ck)) if t in orig and (not want or t in want)]
    q = queue.Queue(); [q.put(t) for t in tasks]
    out, lock = {}, threading.Lock()

    def lane(url):
        env = dict(os.environ, AGENT_API=url.rstrip("/") + "/v1/chat/completions")
        while True:
            try:
                t = q.get_nowait()
            except queue.Empty:
                return
            env["RESUME_FROM"] = os.path.join(ck, t)
            r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "eval.py"), prof, t], env=env, capture_output=True, text=True)
            ok = " PASS " in r.stdout
            with lock:
                out[t] = ok
                print(f"{t:20s} base {'PASS' if orig[t] else 'fail'} -> {prof} {'PASS' if ok else 'fail'}", flush=True)

    th = [threading.Thread(target=lane, args=(u,)) for u in LANES]
    [x.start() for x in th]; [x.join() for x in th]
    b = sum(orig[t] for t in tasks); n = sum(out.values())
    print(f"== stage2 {prof}: base {b}/{len(tasks)} -> {n}/{len(tasks)}", flush=True)


if __name__ == "__main__":
    main()
