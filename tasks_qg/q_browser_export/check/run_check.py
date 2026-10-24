"""Hidden check: start the app with other data/credentials and slow random delays, run the agent's export, compare bytes."""
import json, os, shutil, socket, subprocess, sys, time

PORT = 8799
data = json.load(open("/check/orders_hidden.json", encoding="utf-8"))


def field(v):
    v = str(v)
    return '"' + v.replace('"', '""') + '"' if ("," in v or '"' in v) else v


rows = sorted(data["orders"], key=lambda o: o["id"])
want = "order_id,customer,amount,status,owner,note\n" + "".join(
    ",".join(field(o[k]) for k in ("id", "customer", "amount", "status", "owner", "note")) + "\n" for o in rows)

srv = subprocess.Popen([sys.executable, "/check/app/server.py", "--port", str(PORT), "--data", "/check/orders_hidden.json",
                        "--delay", "100,700", "--seed", "7"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError:
            time.sleep(0.1)
    shutil.rmtree("/work/out", ignore_errors=True)
    env = dict(os.environ, APP_URL=f"http://127.0.0.1:{PORT}", EXPORT_USER=data["user"]["name"], EXPORT_PASS=data["user"]["password"])
    try:
        r = subprocess.run([sys.executable, "automation/export.py"], cwd="/work", env=env, capture_output=True, text=True, timeout=22)
    except subprocess.TimeoutExpired:
        print("export.py did not finish within 22 s"); sys.exit(1)
    if r.returncode != 0:
        print("export.py exit code", r.returncode, (r.stdout + r.stderr)[-800:]); sys.exit(1)
    # graded: one item per expected CSV line (in its place), one for the stdout message, one for no BOM
    msg_ok = f"exported {len(rows)} orders" in r.stdout
    try:
        got = open("/work/out/orders.csv", "rb").read()
    except OSError:
        got = None
    wl0 = want.split("\n")
    if got is None:
        print(f"SCORE {int(msg_ok)}/{len(wl0) + 2}")
    else:
        gl0 = got.decode("utf-8", "replace").split("\n")
        same = sum(1 for i, w in enumerate(wl0) if i < len(gl0) and gl0[i] == w) - max(0, len(gl0) - len(wl0))
        nobom = int(not got.startswith(b"\xef\xbb\xbf"))   # outside the f-string: backslashes there need Python 3.12
        print(f"SCORE {max(0, same) + int(msg_ok) + nobom}/{len(wl0) + 2}")
    if not msg_ok:
        print("stdout lacks 'exported N orders':", r.stdout[-300:]); sys.exit(1)
    if got is None:
        print("out/orders.csv was not written"); sys.exit(1)
    if got.startswith(b"\xef\xbb\xbf"):
        print("out/orders.csv has a BOM"); sys.exit(1)
    g = got.decode("utf-8", "replace")
    if g != want:
        gl, wl = g.split("\n"), want.split("\n")
        bad = [i for i in range(max(len(gl), len(wl))) if (gl[i] if i < len(gl) else None) != (wl[i] if i < len(wl) else None)]
        print(f"out/orders.csv differs on {len(bad)} line(s); first:")
        for i in bad[:4]:
            print(f"  line {i + 1}: want {wl[i] if i < len(wl) else '<none>'!r} got {gl[i] if i < len(gl) else '<none>'!r}")
        sys.exit(1)
    print(f"ok: {len(rows)} orders exported exactly")
finally:
    srv.terminate()
