#!/usr/bin/env python3
"""Live anomaly watcher: follows every runs/*/<task>/log.jsonl and prints one line per finished task and per
anomaly (repeat storms, broken tool calls, errors, long no-progress streaks). Meant to be piped into a monitor."""
import glob, json, os, time

seen, state = {}, {}
while True:
    for f in glob.glob(os.path.expanduser("~/llm/local-agent/runs/*/*/log.jsonl")):
        if time.time() - os.path.getmtime(f) > 3600 and f not in seen:
            seen[f] = os.path.getsize(f); continue
        pos = seen.get(f, 0)
        if os.path.getsize(f) <= pos:
            continue
        run, task = f.split("/")[-3], f.split("/")[-2]
        st = state.setdefault(f, {"rep": 0, "flagged": set()})
        with open(f) as fh:
            fh.seek(pos)
            for line in fh:
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                tag = None
                if "repeat_described" in d or "dropped_repeat" in d:
                    st["rep"] += 1
                    if st["rep"] in (5, 10):
                        tag = f"REPEATS x{st['rep']}"
                elif "step" in d and d.get("calls"):
                    st["rep"] = 0
                if "broken_tool_call" in d:
                    tag = "BROKEN_TOOL_CALL"
                if "result" in d:
                    r = d["result"]
                    tag = f"{'PASS' if r.get('pass') else 'FAIL'} steps={r.get('steps')} fin={r.get('finished')} t={r.get('seconds')}" + (f" error={r['error'][:80]}" if r.get("error") else "")
                if tag:
                    print(f"[{run}] {task}: {tag}", flush=True)
            seen[f] = fh.tell()
    time.sleep(10)
