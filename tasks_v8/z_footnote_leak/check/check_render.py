"""Hidden check: batch / repeated rendering must equal fresh single renders (expected/*.html)."""
import glob, os, shutil, subprocess, sys

sys.path.insert(0, "/work")
os.chdir("/work")
EXP = {os.path.basename(p)[:-5]: open(p, encoding="utf-8").read() for p in glob.glob("/check/expected/*.html")}
SRC = {n: (f"/check/docs/{n}.txt" if os.path.exists(f"/check/docs/{n}.txt") else f"/work/examples/{n}.txt") for n in EXP}
bad = []

def py(*a):
    return subprocess.run([sys.executable, "-m", "docrender", *a], capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH="/work"))

# 1. single renders in fresh processes
for n in ["api", "faq"]:
    r = py("render", SRC[n])
    if r.returncode != 0 or r.stdout != EXP[n]:
        bad.append(f"render {n}: output differs from expected")
# 2. batch in several orders
orders = [["api", "ops", "faq", "notes"], ["notes", "faq", "ops", "api", "onboarding", "release", "style"],
          ["ops", "ops", "api", "api"], ["style", "release", "onboarding", "api"]]
for k, order in enumerate(orders):
    out = f"/tmp/out{k}"
    shutil.rmtree(out, ignore_errors=True)
    r = py("batch", *[SRC[n] for n in order], "-o", out)
    if r.returncode != 0:
        bad.append(f"batch {order}: exit {r.returncode} {r.stderr[-200:]}")
        continue
    for n in set(order):
        got = open(f"{out}/{n}.html", encoding="utf-8").read()
        if got != EXP[n]:
            bad.append(f"batch {order}: {n}.html differs from a single render")
# 3. same process, API
from docrender import render
texts = {n: open(SRC[n], encoding="utf-8").read() for n in EXP}
for rnd in range(2):
    for n in ["ops", "api", "notes", "faq", "onboarding", "api", "release", "style"]:
        if render(texts[n]) != EXP[n]:
            bad.append(f"render() round {rnd}: {n} differs when rendered after other documents")
print(f"{len(bad)} problems")
for b in sorted(set(bad))[:8]:
    print(" ", b)
sys.exit(1 if bad else 0)
