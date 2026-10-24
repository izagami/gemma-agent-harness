"""Hidden check: run the agent's submit.py against the app with other rows, credentials and slow random delays;
the server's stored records must be exactly the CSV rows, once each, and stdout must report each number."""
import csv, json, os, socket, subprocess, sys, time

PORT, STORE = 8798, "/tmp/store_check.json"
CODES = {"経理部": "acct", "営業部": "sales", "開発部": "dev", "人事部": "hr"}
rows = list(csv.DictReader(open("/check/apps_hidden.csv", encoding="utf-8", newline="")))
want = [{"no": f"A-{i + 1:04d}", "name": r["氏名"], "email": r["メール"], "dept": CODES[r["部署"]],
         "amount": int(r["金額"].replace(",", "")), "reason": r["理由"]} for i, r in enumerate(rows)]
if os.path.exists(STORE):
    os.remove(STORE)
srv = subprocess.Popen([sys.executable, "/check/app/server.py", "--port", str(PORT), "--store", STORE,
                        "--delay", "300,1500", "--seed", "11", "--user", "kensa:Pa55-word!"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError:
            time.sleep(0.1)
    env = dict(os.environ, APP_URL=f"http://127.0.0.1:{PORT}", APP_USER="kensa", APP_PASS="Pa55-word!")
    try:
        r = subprocess.run([sys.executable, "automation/submit.py", "/check/apps_hidden.csv"], cwd="/work", env=env,
                           capture_output=True, text=True, timeout=24)
    except subprocess.TimeoutExpired:
        print("submit.py did not finish within 24 s"); sys.exit(1)
    got = json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else []
    # graded: one item per expected record (stored in its place) + one for the documented stdout
    rec_ok = sum(1 for i, w in enumerate(want) if i < len(got) and got[i] == w) - max(0, len(got) - len(want))
    out = r.stdout.splitlines()
    need = [f"OK {w['name']} {w['no']}" for w in want] + [f"registered {len(want)}"]
    out_ok = int([l for l in out if l.startswith(("OK ", "registered"))] == need)
    print(f"SCORE {max(0, rec_ok) + out_ok}/{len(want) + 1}")
    if r.returncode != 0:
        print("submit.py exit code", r.returncode, f"({len(got)} records stored)", (r.stdout + r.stderr)[-600:]); sys.exit(1)
    if got != want:
        print(f"stored records differ: {len(got)} stored, {len(want)} expected")
        for i in range(max(len(got), len(want))):
            g, w = (got[i] if i < len(got) else None), (want[i] if i < len(want) else None)
            if g != w:
                print("  first difference: want", w, "got", g); break
        sys.exit(1)
    if not out_ok:
        print("stdout differs from the documented format; want", need[:2], "... got", out[:3]); sys.exit(1)
    print(f"ok: {len(want)} applications registered exactly once")
finally:
    srv.terminate()
