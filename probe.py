#!/usr/bin/env python3
"""Propose-probe step (after Harness²): run a few tasks under several harness profiles side by side and
contrast how each one behaved, not just whether it passed.

usage: probe.py [-r REPEATS] PROFILES TASKS      e.g. probe.py -r 2 v7e,v7f,v7g y_timesheet,y_tzreport
servers: LANES (same as evalmulti.py). Writes runs/probe-<time>/{<profile>/<task>-<n>/..., summary.md}.

Behaviour per run: pass, finished, steps, time, tool mix, repeats refused, finish rejections, nudges,
cut-off calls, file writes, and the last actions. Use it on the failing tasks before a full-suite run;
record the outcome in docs/EXPERIENCE.md.
"""
import collections, json, os, queue, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.environ.get("TASKS_DIR", os.path.join(HERE, "tasks"))
LANES = os.environ.get("LANES", "http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087").split(",")


def behaviour(logpath):
    tools, ev, last = collections.Counter(), collections.Counter(), []
    res = {}
    for line in open(logpath, encoding="utf-8"):
        d = json.loads(line)
        if "result" in d:
            res = d["result"]
        elif "step" in d and d.get("calls"):
            for n, a in d["calls"]:
                tools[n] += 1
                try:
                    a = json.loads(a)
                except ValueError:
                    a = {}
                desc = a.get("command") or a.get("path") or a.get("thought") or ""
                last.append(f"{d['step']}:{n} {str(desc)[:70]!r}")
        else:
            for k in ("repeat_described", "broken_tool_call", "finish_rejected", "stagnation_nudge", "progress_nudge", "nudge"):
                if k in d:
                    ev[k] += 1
    return {"pass": res.get("pass"), "finished": res.get("finished"), "steps": res.get("steps"), "seconds": res.get("seconds"),
            "tools": dict(tools), "events": dict(ev), "last": last[-6:]}


def main():
    argv = sys.argv[1:]
    reps = 1
    if argv[0] == "-r":
        reps, argv = int(argv[1]), argv[2:]
    profiles, tasks = argv[0].split(","), argv[1].split(",")
    jobs = [(p, t, i) for i in range(reps) for t in tasks for p in profiles]  # interleave so profiles share lanes fairly
    q = queue.Queue(); [q.put(j) for j in jobs]
    out = os.path.join(HERE, "runs", "probe-" + time.strftime("%m%d-%H%M%S"))
    os.makedirs(out)
    results, lock = [], threading.Lock()

    def lane(url):
        env = dict(os.environ, AGENT_API=url.rstrip("/") + "/v1/chat/completions")
        while True:
            try:
                p, t, i = q.get_nowait()
            except queue.Empty:
                return
            r = subprocess.run([sys.executable, "-u", os.path.join(HERE, "eval.py"), p, t], env=env, capture_output=True, text=True)
            sub = [l for l in r.stdout.splitlines() if l.startswith("== ")]
            d = sub[-1].rsplit("(", 1)[-1].rstrip(")") if sub else None
            if not d or not os.path.exists(os.path.join(d, t, "log.jsonl")):
                print(f"{p:6s} {t:16s} #{i} ERROR {r.stderr[-300:]}", flush=True)
                continue
            dest = os.path.join(out, p, f"{t}-{i}")
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            os.rename(os.path.join(d, t), dest)
            for f in os.listdir(d):
                os.remove(os.path.join(d, f))
            os.rmdir(d)
            b = behaviour(os.path.join(dest, "log.jsonl"))
            with lock:
                results.append((p, t, i, b))
                print(f"{p:6s} {t:16s} #{i} {'PASS' if b['pass'] else 'fail'} steps={b['steps']} t={b['seconds']} "
                      f"events={b['events']}", flush=True)

    th = [threading.Thread(target=lane, args=(u,)) for u in LANES]
    [x.start() for x in th]; [x.join() for x in th]

    md = [f"# Probe {os.path.basename(out)}\n", f"profiles {profiles}, tasks {tasks}, repeats {reps}\n"]
    for t in tasks:
        md.append(f"\n## {t}\n\n| profile | run | pass | steps | s | tools | events |\n|---|---|---|---|---|---|---|")
        for p, tt, i, b in sorted(results, key=lambda x: (x[0], x[2])):
            if tt == t:
                md.append(f"| {p} | {i} | {'PASS' if b['pass'] else 'fail'} | {b['steps']} | {b['seconds']} | "
                          f"{' '.join(f'{k}:{v}' for k, v in sorted(b['tools'].items()))} | "
                          f"{' '.join(f'{k}:{v}' for k, v in sorted(b['events'].items()))} |")
        for p, tt, i, b in sorted(results, key=lambda x: (x[0], x[2])):
            if tt == t:
                md.append(f"\n{p} #{i} last actions: " + " / ".join(b["last"]))
    md.append("\n## Pass rate\n")
    for p in profiles:
        rs = [b["pass"] for pp, _, _, b in results if pp == p]
        md.append(f"- {p}: {sum(bool(x) for x in rs)}/{len(rs)}")
    open(os.path.join(out, "summary.md"), "w").write("\n".join(md) + "\n")
    print("\n".join(md[-len(profiles) - 1:]), f"\n({out}/summary.md)", flush=True)


if __name__ == "__main__":
    main()
