#!/usr/bin/env python3
"""Step-level temperature sweep: from saved mid-task states, sample the next step several times per temperature with
the real action path (agent_v5.chat_stream, typed think fused with the action) and count per-step properties that
need no judgment: a valid tool call, plain text / cut-off calls, repeating the previous action, agreement between
samples, time. Task-level runs are too noisy to tune a sampling parameter (10-24).
usage: tempsweep.py SHARD NSHARDS OUT.jsonl      (env: AGENT_API = one lane; TEMPS, SAMPLES, CUTS)"""
import glob, json, os, pickle, sys, time
from concurrent.futures import ThreadPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
os.environ.setdefault("THINK_SCHEMA", "3"); os.environ.setdefault("THINK_LEARNED", "800"); os.environ.setdefault("THINK_NEXT", "400")
import agent_v5 as A, agent as base

shard, nsh, out = int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]
TEMPS = [float(t) for t in os.environ.get("TEMPS", "0,0.3,0.6,1.0").split(",")]
SAMPLES, CUTS = int(os.environ.get("SAMPLES", "4")), int(os.environ.get("CUTS", "6"))
states = []
for f in sorted(glob.glob(os.path.join(HERE, "runs", "ckpt-v7x-2", "*", "ckpt.pkl"))):
    m = [{k: v for k, v in x.items() if k in ("role", "content", "tool_calls", "tool_call_id", "name")}
         for x in pickle.load(open(f, "rb"))["messages"]]
    cuts = [k for k in range(4, len(m)) if m[k - 1]["role"] in ("tool", "user") and m[k]["role"] == "assistant"]
    pick = [cuts[int(i * (len(cuts) - 1) / max(CUTS - 1, 1))] for i in range(CUTS)] if len(cuts) >= CUTS else cuts
    for k in sorted(set(pick)):
        states.append((os.path.basename(os.path.dirname(f)), k, m[:k]))
states = states[shard::nsh]


def prev_action(msgs):
    for x in reversed(msgs):
        for c in reversed(x.get("tool_calls") or []):
            if c["function"]["name"] != "think":
                return (c["function"]["name"], c["function"]["arguments"])
    return None


def one(job):
    (task, k, msgs), T, s = job
    t0 = time.time()
    try:
        ch = A.chat_stream(msgs, A.TOOLS + [A.THINK_TOOL], max_tokens=4096, temperature=T, typed=True, fuse=True)
        calls = [c for c in ch["message"].get("tool_calls") or [] if c["function"]["name"] != "think"]
        thought = any(c["function"]["name"] == "think" for c in ch["message"].get("tool_calls") or [])
        if calls:
            a = calls[0]["function"]
            try:
                json.loads(a["arguments"] or "{}"); kind = "call"
            except ValueError:
                kind = "badjson"
            act = (a["name"], a["arguments"])
        else:
            kind, act = ("text" if (ch["message"].get("content") or "").strip() else "empty"), None
        fr = ch.get("finish_reason")
    except base.BrokenToolCall:
        kind, act, thought, fr = "broken", None, False, "broken"
    except Exception as e:
        kind, act, thought, fr = "error:" + type(e).__name__, None, False, str(e)[:100]
    return dict(task=task, k=k, T=T, s=s, kind=kind, act=act, think=thought, finish=fr, repeat=act is not None and act == prev_action(msgs),
                sec=round(time.time() - t0, 1))


jobs = [(st, T, s) for st in states for T in TEMPS for s in range(SAMPLES)]
with ThreadPoolExecutor(int(os.environ.get("WORKERS", "4"))) as ex, open(out, "w") as fh:
    for r in ex.map(one, jobs):
        fh.write(json.dumps(r, ensure_ascii=False) + "\n"); fh.flush()
print("done", len(jobs))
