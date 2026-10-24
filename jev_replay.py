#!/usr/bin/env python3
"""Stage 1 of the fast loop: score the evidence + Jev gate on finished results whose hidden-check verdict is known.
usage: jev_replay.py [--suite q] [--limit N] [--out runs/replay/scores.jsonl]
For every requirement of every result: p(violated). A good gate flags failing results and leaves passing ones alone."""
import argparse, concurrent.futures as cf, glob, json, os, shutil, sys, time
import agent as base, agent_g as G, evidence, eval as E

HERE = os.path.dirname(os.path.abspath(__file__))

Q = ("Task given to an engineer:\n<task>\n{task}\n</task>\n\nOne requirement of the task:\n{req}\n\n"
     "Facts about the engineer's finished result, collected automatically by running it (not written by the engineer):\n"
     "<facts>\n{facts}\n</facts>\n\nDo these facts clearly show that the result violates this requirement? Answer "
     "violated=false if the facts show it is met, or if they say nothing about this requirement.")


QM = ("Task given to an engineer:\n<task>\n{task}\n</task>\n\nOne requirement of the task:\n{req}\n\n"
      "Facts about the engineer's finished result, collected automatically by running it:\n<facts>\n{facts}\n</facts>\n\n"
      "Are these facts consistent with the requirement being met? Answer consistent=false only if a fact shown above "
      "directly contradicts the requirement.")

QD = ("One requirement of a task:\n{req}\n\nFacts collected automatically from the engineer's finished result:\n"
      "<facts>\n{facts}\n</facts>\n\nCan a reader decide whether this requirement is met just by reading these facts, "
      "with no calculation of their own, no guessing about inputs not shown, and no knowledge of the code? "
      "Answer decidable=true only if so.")


def reqs_by_task():
    """fresh extraction per task (agent_v5.extract_reqs), cached in runs/replay/reqs.json"""
    import agent_v5
    cache = os.path.join(HERE, "runs", "replay", "reqs.json")
    out = json.load(open(cache)) if os.path.exists(cache) else {}
    for tid in sorted(os.listdir(os.path.join(HERE, "tasks_q"))):
        if tid not in out:
            st = agent_v5.State(); st.workdir = os.path.join(HERE, "tasks_q", tid, "files")
            out[tid] = agent_v5.extract_reqs(st, open(os.path.join(HERE, "tasks_q", tid, "task.md")).read())
            json.dump(out, open(cache, "w"), ensure_ascii=False, indent=0)
    return out


def reqs_from_v7r():
    out = {}
    for f in sorted(glob.glob(os.path.join(HERE, "runs", "v7r-*", "*", "log.jsonl"))):
        for l in open(f):
            if l.startswith('{"reqs"'):
                out.setdefault(f.split("/")[-2], json.loads(l)["reqs"]); break
    return out


def labeled(prefix):
    out = []
    for f in sorted(glob.glob(os.path.join(HERE, "runs", "*", prefix + "*", "log.jsonl"))):
        d = os.path.dirname(f)
        if "/replay/" in d or "audit-try" in d or not os.path.isdir(os.path.join(d, "work")):
            continue
        res = next((json.loads(l)["result"] for l in open(f, errors="replace") if l.startswith('{"result"')), None)
        if res:
            out.append((d, res["task"], res["pass"]))
    return out


def one(item, reqs, tasks_dir):
    d, tid, ok = item
    src = os.path.join(tasks_dir, tid)
    dst = os.path.join(HERE, "runs", "replay", d.split("/")[-2] + "_" + tid)
    shutil.rmtree(dst, ignore_errors=True)
    shutil.copytree(os.path.join(d, "work"), os.path.join(dst, "work"), symlinks=True)
    img, mounts = E.sandbox_conf(src)
    if img:
        base.SANDBOX_FOR[dst] = (img, mounts)
    task = open(os.path.join(src, "task.md")).read()
    facts = evidence.collect(os.path.join(dst, "work"), os.path.join(src, "files"), task)
    bad, sc = evidence.judge_reqs(task, reqs[tid], facts, evidence.docs_text(os.path.join(src, "files")))
    return {"run": d.split("/")[-2], "task": tid, "pass": ok, "bad": bad, "scores": sc, "facts": facts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suite", default="q")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(HERE, "runs", "replay", "scores.jsonl"))
    ap.add_argument("--tasks", default="")
    ap.add_argument("-j", type=int, default=6, help="results scored at once (evidence collection is the slow part)")
    a = ap.parse_args()
    reqs = reqs_by_task()
    items = [x for x in labeled("q_") if x[1] in reqs and (not a.tasks or x[1] in a.tasks.split(","))]
    if a.limit:
        items = items[:a.limit]
    done = set()
    if os.path.exists(a.out):   # resume: skip results already scored into this file
        for l in open(a.out):
            r = json.loads(l); done.add((r["run"], r["task"]))
    todo = [x for x in items if (x[0].split("/")[-2], x[1]) not in done]
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    print(f"{len(items)} results ({sum(x[2] for x in items)} passing)", flush=True)
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.j) as ex, open(a.out, "a") as f:
        for r in ex.map(lambda x: one(x, reqs, os.path.join(HERE, "tasks_q")), todo):
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
            print(f"{r['task']:20s} {'PASS' if r['pass'] else 'fail'} flagged {len(r['bad'])} of {r['scores']['n']}", flush=True)
    R = [json.loads(l) for l in open(a.out)]
    P = [r for r in R if r["pass"]]; F = [r for r in R if not r["pass"]]
    print(f"== passing flagged {sum(bool(r['bad']) for r in P)}/{len(P)}, failing caught {sum(bool(r['bad']) for r in F)}/{len(F)}, "
          f"{round(time.time() - t0)} s", flush=True)


if __name__ == "__main__":
    main()
