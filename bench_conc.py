#!/usr/bin/env python3
"""Throughput of a server under agent-like load: real agent conversations (finish checkpoints in runs/ckpt-v7x-2)
sent C at a time, each once and then again with one more turn appended (what an agent does every step: the same
long prefix plus a little).

usage: bench_conc.py URL C [C ...]      e.g. bench_conc.py http://127.0.0.1:8087 1 4 8 16
prints per C: wall seconds, aggregate output tok/s, mean prompt tokens, mean time to first answer
"""
import glob, json, os, pickle, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import agent_v5

CONVS = []
for f in sorted(glob.glob(os.path.join(HERE, "runs", "ckpt-v7x-2", "*", "ckpt.pkl"))):
    m = pickle.load(open(f, "rb"))["messages"]
    CONVS.append([{k: v for k, v in x.items() if k in ("role", "content", "tool_calls", "tool_call_id", "name")} for x in m])


def ask(url, msgs, max_tokens=200):
    body = {"model": "gemma4", "messages": msgs, "tools": agent_v5.TOOLS, "max_tokens": max_tokens, "temperature": 1.0,
            "top_p": 0.95}
    req = urllib.request.Request(url.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    t = time.time()
    r = json.load(urllib.request.urlopen(req, timeout=900))
    u = r.get("usage", {})
    return time.time() - t, u.get("prompt_tokens", 0), u.get("completion_tokens", 0)


def run(url, c):
    jobs = [CONVS[i % len(CONVS)] for i in range(c)]
    jobs = jobs + [j + [{"role": "user", "content": "[harness] Continue. If everything is verified, call finish."}] for j in jobs]
    t0 = time.time()
    with ThreadPoolExecutor(c) as ex:
        first = list(ex.map(lambda m: ask(url, m), jobs[:c]))
        second = list(ex.map(lambda m: ask(url, m), jobs[c:]))
    wall = time.time() - t0
    out = sum(x[2] for x in first + second)
    print(f"C={c:2d} wall {wall:6.1f} s  out {out / wall:6.1f} tok/s  prompt {sum(x[1] for x in first) / c:6.0f} tok  "
          f"latency 1st {sum(x[0] for x in first) / c:5.1f} s  2nd (cached prefix) {sum(x[0] for x in second) / c:5.1f} s", flush=True)


if __name__ == "__main__":
    url = sys.argv[1]
    for c in map(int, sys.argv[2:]):
        run(url, c)
