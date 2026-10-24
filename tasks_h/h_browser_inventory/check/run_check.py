"""Hidden check: run the agent's inventory.py against the app with more warehouses (one with only zero/negative stock),
tricky item names, another user and slow random delays; out/inventory.csv must equal the expected bytes."""
import csv, io, json, os, shutil, socket, subprocess, sys, time

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

PORT = free_port()
data = json.load(open("/check/stock_hidden.json", encoding="utf-8"))
want_rows = sorted(((w["code"], it["sku"], it["name"], str(it["qty"])) for w in data["warehouses"] for it in w["items"]),
                   key=lambda r: (r[0], r[1]))
buf = io.StringIO()
wr = csv.writer(buf, lineterminator="\n")
wr.writerow(["warehouse", "sku", "name", "qty"])
wr.writerows(want_rows)
want_bytes = buf.getvalue().encode("utf-8")

shutil.rmtree("/work/out", ignore_errors=True)
srv = subprocess.Popen([sys.executable, "/check/app/server.py", "--port", str(PORT), "--data", "/check/stock_hidden.json",
                        "--delay", "50,400", "--seed", "5", "--user", "tanaoroshi:K7#q,9zX"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError:
            time.sleep(0.1)
    env = dict(os.environ, APP_URL=f"http://127.0.0.1:{PORT}", STOCK_USER="tanaoroshi", STOCK_PASS="K7#q,9zX")
    try:
        r = subprocess.run([sys.executable, "automation/inventory.py"], cwd="/work", env=env,
                           capture_output=True, text=True, timeout=40)
    except subprocess.TimeoutExpired:
        print("SCORE 0/%d" % (len(want_rows) + 1)); print("inventory.py did not finish within 40 s"); sys.exit(1)
    path = "/work/out/inventory.csv"
    got_bytes = open(path, "rb").read() if os.path.exists(path) else b""
    try:
        got = list(csv.reader(io.StringIO(got_bytes.decode("utf-8-sig"), newline="")))
    except Exception as e:
        got = []; print("cannot parse out/inventory.csv:", e)
    body = [tuple(x) for x in got[1:]]
    from collections import Counter
    cnt, wantset = Counter(body), set(want_rows)
    good = sum(1 for w in want_rows if cnt[w] == 1)
    extra = sum(c for row, c in cnt.items() if row not in wantset) + sum(c - 1 for row, c in cnt.items() if row in wantset and c > 1)
    stdout_ok = f"exported {len(want_rows)} items" in r.stdout
    fmt_ok = int(got_bytes == want_bytes and stdout_ok)
    print(f"SCORE {max(0, good - extra) + fmt_ok}/{len(want_rows) + 1}")
    if r.returncode != 0:
        print("inventory.py exit code", r.returncode, (r.stdout + r.stderr)[-600:]); sys.exit(1)
    if got_bytes != want_bytes:
        print(f"out/inventory.csv differs: {len(body)} data rows, {len(want_rows)} expected; {good} correct, {extra} extra/duplicate")
        if got_bytes.startswith(b"\xef\xbb\xbf"): print("  file starts with a BOM")
        if b"\r\n" in got_bytes: print("  CRLF line ends")
        if got and got[0] != ["warehouse", "sku", "name", "qty"]: print("  header:", got[0])
        missing = [w for w in want_rows if cnt[w] == 0]
        if missing: print(f"  {len(missing)} missing, e.g.", missing[:3])
        wrong = [row for row in cnt if row not in wantset]
        if wrong: print("  unexpected rows, e.g.", wrong[:3])
        if not missing and not wrong and body != want_rows: print("  order differs")
        sys.exit(1)
    if not stdout_ok:
        print("stdout lacks", f"'exported {len(want_rows)} items'; got", r.stdout[-200:]); sys.exit(1)
    print(f"ok: {len(want_rows)} items exported")
finally:
    srv.terminate()
