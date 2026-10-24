#!/usr/bin/env python3
"""Validate the v8 suite: every hidden check must FAIL on the untouched seed and PASS (twice) on the reference.

usage: validate_v8.py [-jN] [task ...]     (checks run exactly like eval.py: eval.check() in the podman sandbox)
"""
import os, shutil, subprocess, sys, tempfile, time
from concurrent.futures import ThreadPoolExecutor
import eval as ev
import tasks_v8


def seed_stats(tid):
    n = lines = 0
    for root, dirs, files in os.walk(os.path.join(tasks_v8.SRC, tid, "seed")):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            n += 1
            with open(os.path.join(root, f), "rb") as fh:
                lines += fh.read().count(b"\n")
    return n, lines


def timed_check(work, chk):
    t = time.time()
    ok, out = ev.check(work, chk)
    return ok, out, time.time() - t


def one(tid, tmp):
    base = os.path.join(tmp, tid)
    tasks_v8.build_one(tid, base)
    chk = os.path.join(base, "check")
    # 1. seed must fail
    ws = os.path.join(tmp, tid + "-seed")
    shutil.copytree(os.path.join(base, "files"), ws)
    s_ok, s_out, s_t = timed_check(ws, chk)
    # 2. reference must pass (twice, fresh copies: determinism)
    r = []
    for i in range(2):
        wr = os.path.join(tmp, f"{tid}-ref{i}")
        shutil.copytree(os.path.join(base, "files"), wr)
        shutil.copytree(os.path.join(tasks_v8.SRC, tid, "ref"), wr, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        cmd = os.path.join(tasks_v8.SRC, tid, "ref_cmd.sh")
        if os.path.exists(cmd):
            subprocess.run(["podman", "run", "--rm", "--network", "none", "--userns=keep-id", "-v", f"{wr}:/work:Z",
                            "-w", "/work", ev.agent.IMAGE, "bash", "-c", open(cmd).read()], check=True)
        r.append(timed_check(wr, chk))
    return tid, s_ok, s_out, s_t, r


def main():
    argv = sys.argv[1:]
    jobs = 4
    if argv and argv[0].startswith("-j"):
        jobs = int(argv.pop(0)[2:])
    tids = argv or tasks_v8.ids()
    tmp = tempfile.mkdtemp(prefix="v8val-")
    try:
        with ThreadPoolExecutor(jobs) as ex:
            res = list(ex.map(lambda t: one(t, tmp), tids))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = 0
    print(f"{'task':20s} {'kind':12s} {'files':>5s} {'lines':>6s}  {'seed':10s} {'ref#1':10s} {'ref#2':10s} valid")
    for tid, s_ok, s_out, s_t, r in res:
        kind = tasks_v8.TASKS.get(tid, ("?", ""))[0]
        n, lines = seed_stats(tid)
        valid = (not s_ok) and all(ok for ok, _, _ in r) and max(s_t, *(t for _, _, t in r)) < 30
        bad += not valid
        f = lambda ok, t: f"{'PASS' if ok else 'fail'} {t:4.1f}s"
        print(f"{tid:20s} {kind:12s} {n:5d} {lines:6d}  {f(s_ok, s_t):10s} {f(*r[0][::2]):10s} {f(*r[1][::2]):10s} {'OK' if valid else 'INVALID'}")
    for tid, s_ok, s_out, s_t, r in res:
        def tail(o):
            ls = o.strip().splitlines()
            bad = [l for l in ls if any(k in l for k in ("Error", "assert", "FAIL", "fail", "modified", "differ", "!=", "Traceback", "missing", "not "))]
            return " | ".join((bad or ls)[-3:])[-300:]
        print(f"  {tid}: seed-> {tail(s_out)}")
        for ok, out, _ in r:
            if not ok:
                print(f"  {tid}: REF FAILED-> {tail(out)}")
    print(f"== {len(res) - bad}/{len(res)} tasks valid")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
