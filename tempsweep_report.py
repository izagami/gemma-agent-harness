#!/usr/bin/env python3
"""Summarize tempsweep.py output: per temperature, rates of valid calls / text / broken, repeats of the previous
action, agreement between samples at the same state (share of samples equal to the state's most common action),
think use and seconds per step. usage: tempsweep_report.py OUT.jsonl [...]"""
import collections, json, sys
R = [json.loads(l) for f in sys.argv[1:] for l in open(f)]
by = collections.defaultdict(list)
for r in R:
    by[r["T"]].append(r)
print(f"{len(R)} samples, {len({(r['task'], r['k']) for r in R})} states")
print("temp  n    call%  text%  broken%  repeat%  same-as-mode%  same-tool%  think%  s/step")
for T in sorted(by):
    rs = by[T]; n = len(rs)
    st = collections.defaultdict(list)
    for r in rs:
        st[(r["task"], r["k"])].append(r)
    agree = tool_agree = tot = 0
    for v in st.values():
        acts = [json.dumps(r["act"]) for r in v]
        tools = [r["act"][0] if r["act"] else None for r in v]
        agree += collections.Counter(acts).most_common(1)[0][1]
        tool_agree += collections.Counter(tools).most_common(1)[0][1]
        tot += len(v)
    pct = lambda f: 100 * sum(1 for r in rs if f(r)) / n
    print(f"{T:4.1f} {n:5d}  {pct(lambda r: r['kind'] == 'call'):5.1f}  {pct(lambda r: r['kind'] in ('text', 'empty')):5.1f}  "
          f"{pct(lambda r: r['kind'] in ('broken', 'badjson') or r['kind'].startswith('error')):6.1f}  {pct(lambda r: r['repeat']):6.1f}  "
          f"{100 * agree / tot:12.1f}  {100 * tool_agree / tot:9.1f}  {pct(lambda r: r['think']):5.1f}  {sum(r['sec'] for r in rs) / n:5.1f}")
