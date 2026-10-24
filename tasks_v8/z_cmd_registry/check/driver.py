"""Run many `python3 -m invtool ...` invocations in one interpreter (speed). usage: driver.py WORKDIR SCRIPT.json"""
import base64, io, json, os, runpy, sys

work, script = sys.argv[1], json.load(open(sys.argv[2]))
os.chdir(work)
res = []
real = sys.stdout, sys.stderr
for args in script:
    out, err = io.BytesIO(), io.BytesIO()
    sys.stdout = io.TextIOWrapper(out, encoding="utf-8", newline="")
    sys.stderr = io.TextIOWrapper(err, encoding="utf-8", newline="")
    sys.argv = ["invtool", *args]
    code = 0
    try:
        runpy.run_module("invtool", run_name="__main__", alter_sys=True)
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else (0 if e.code is None else 1)
    sys.stdout.flush(); sys.stderr.flush()
    o, e = out.getvalue(), err.getvalue()
    sys.stdout, sys.stderr = real
    res.append([args, code, base64.b64encode(o).decode(), base64.b64encode(e).decode()])
json.dump(res, sys.stdout)
