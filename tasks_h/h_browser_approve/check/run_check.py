"""Hidden check: run the agent's approve.py against the app with more requests (numbers that are substrings of each other),
comments with commas/quotes, already processed requests, another user and slow random delays. Graded on the server's
store: each listed request handled correctly with exactly one approve operation, nothing else touched, stdout format."""
import copy, csv, json, os, socket, subprocess, sys, time

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

PORT, STORE, USER, PASS = free_port(), "/tmp/approve_store_check.json", "keiri02", "s3cret,\"pw\""
orig = json.load(open("/check/requests_hidden.json", encoding="utf-8"))
byno = {r["no"]: r for r in orig}
todo = [(r["申請番号"], r["コメント"]) for r in csv.DictReader(open("/check/approve_hidden.csv", encoding="utf-8", newline=""))]
listed = {no for no, _ in todo}
if os.path.exists(STORE):
    os.remove(STORE)
srv = subprocess.Popen([sys.executable, "/check/app/server.py", "--port", str(PORT), "--data", "/check/requests_hidden.json",
                        "--store", STORE, "--delay", "150,900", "--seed", "4", "--user", f"{USER}:{PASS}"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    for _ in range(100):
        try:
            socket.create_connection(("127.0.0.1", PORT), 0.2).close(); break
        except OSError:
            time.sleep(0.1)
    env = dict(os.environ, APP_URL=f"http://127.0.0.1:{PORT}", APP_USER=USER, APP_PASS=PASS)
    timed_out = False
    try:
        r = subprocess.run([sys.executable, "automation/approve.py", "/check/approve_hidden.csv"], cwd="/work", env=env,
                           capture_output=True, text=True, timeout=42)
    except subprocess.TimeoutExpired as e:
        timed_out, r = True, None
    st = json.load(open(STORE, encoding="utf-8")) if os.path.exists(STORE) else {"requests": copy.deepcopy(orig), "audit": []}
    now = {x["no"]: x for x in st["requests"]}
    audit = st["audit"]
    score, notes, need = 0, [], []
    for no, comment in todo:
        ops = [a for a in audit if a["no"] == no]
        if byno[no]["status"] == "申請中":
            need.append(f"APPROVED {no}")
            good = (now[no]["status"] == "承認済" and now[no]["comment"] == comment and now[no]["approver"] == USER
                    and len(ops) == 1 and ops[0]["result"] == "ok")
            if not good:
                notes.append(f"{no}: want approved once with comment {comment!r}; status={now[no]['status']} "
                             f"comment={now[no]['comment']!r} operations={len(ops)}")
        else:
            need.append(f"SKIP {no} {byno[no]['status']}")
            good = not ops and now[no] == byno[no]
            if not good:
                notes.append(f"{no}: was {byno[no]['status']}, must not be operated on; operations={len(ops)}")
        score += good
    others = [a["no"] for a in audit if a["no"] not in listed]
    changed = [no for no in byno if no not in listed and now[no] != byno[no]]
    score += int(not others and not changed)
    if others or changed:
        notes.append(f"requests not in the list were operated on / changed: {sorted(set(others + changed))[:8]}")
    n_ap = sum(1 for x in need if x.startswith("APPROVED"))
    need.append(f"approved {n_ap} skipped {len(need) - n_ap}")
    out = [l for l in (r.stdout.splitlines() if r else []) if l.startswith(("APPROVED ", "SKIP ", "approved "))]
    out_ok = int(out == need)
    score += out_ok
    # details first (short, at most 6), SCORE last: eval reads the score from the last 1500 chars of the output
    for x in notes[:6]:
        print(" ", str(x)[:200])
    fail = None
    if timed_out:
        fail = "approve.py did not finish within 42 s"
    elif r.returncode != 0:
        fail = "approve.py exit code %s %s" % (r.returncode, (r.stdout + r.stderr)[-300:])
    elif not out_ok:
        fail = "stdout differs; want %s ... got %s" % (need[:3], out[:3])
    elif notes:
        fail = "requests handled wrongly (see above)"
    if fail:
        print(fail)
        print(f"SCORE {score}/{len(todo) + 2}")
        sys.exit(1)
    print(f"SCORE {score}/{len(todo) + 2}")
    print(f"ok: {n_ap} approved, {len(need) - 1 - n_ap} skipped")
finally:
    srv.terminate()
