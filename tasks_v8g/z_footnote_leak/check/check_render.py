"""Hidden check: batch / repeated rendering must equal fresh single renders (expected/*.html)."""
import glob, os, shutil, subprocess, sys

sys.path.insert(0, "/work")
os.chdir("/work")
EXP = {os.path.basename(p)[:-5]: open(p, encoding="utf-8").read() for p in glob.glob("/check/expected/*.html")}
SRC = {n: (f"/check/docs/{n}.txt" if os.path.exists(f"/check/docs/{n}.txt") else f"/work/examples/{n}.txt") for n in EXP}
bad = []
T = [0]  # tasks_v8g items: 2 single renders + one per (batch order, document) + 16 render() calls = 35

def py(*a):
    return subprocess.run([sys.executable, "-m", "docrender", *a], capture_output=True, text=True,
                          env=dict(os.environ, PYTHONPATH="/work"))

# 1. single renders in fresh processes
for n in ["api", "faq"]:
    T[0] += 1
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
    T[0] += len(set(order))
    if r.returncode != 0:
        bad.append(f"batch {order}: exit {r.returncode} {r.stderr[-200:]}")
        bad.extend([f"batch {order}: (not run)"] * (len(set(order)) - 1))  # every document of this batch fails
        continue
    for n in set(order):
        try:  # tasks_v8: a missing output file ended the script (= failure)
            got = open(f"{out}/{n}.html", encoding="utf-8").read()
        except OSError as x:
            got = None
            bad.append(f"batch {order}: {n}.html: {x}")
            continue
        if got != EXP[n]:
            bad.append(f"batch {order}: {n}.html differs from a single render")
# 3. same process, API
try:
    from docrender import render
except Exception as x:  # noqa: BLE001 - tasks_v8: ended the script (= failure); here every render() item fails
    print("import docrender failed:", repr(x)[:300])
    render = None
texts = {n: open(SRC[n], encoding="utf-8").read() for n in EXP}
for rnd in range(2):
    for n in ["ops", "api", "notes", "faq", "onboarding", "api", "release", "style"]:
        T[0] += 1
        try:
            ok = render is not None and render(texts[n]) == EXP[n]
        except Exception as x:  # noqa: BLE001
            ok = False
        if not ok:
            bad.append(f"render() round {rnd}: {n} differs when rendered after other documents")
print(f"{len(bad)} problems")
for b in sorted(set(bad))[:8]:
    print(" ", b)
print(f"ITEMS {T[0] - len(bad)}/{T[0]}")
sys.exit(1 if bad else 0)
