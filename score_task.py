#!/usr/bin/env python3
"""score_task.py TASKDIR WORKDIR -> runs TASKDIR/check/check.sh on WORKDIR exactly as eval.py does (podman, no network,
60 s), prints PASS/fail and the tail of the output. Exit 0 only on PASS."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import eval as E
task, work = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
ok, out = E.check(work, os.path.join(task, "check"))
print("PASS" if ok else "fail")
print(out[-1200:])
sys.exit(0 if ok else 1)
