#!/usr/bin/env python3
"""Watch an evaluation while it runs and exit as soon as something needs attention, so whoever started it is woken
up at once (2026-10-23: a profile-name collision ran 1 h without the feature under test, and a judge stuck at p=1.0
went unseen for another hour, because nobody looked until asked).

usage: watchdog.py PROFILE[;PROFILE2...] [--expect feat,feat] [--out eval-x.out] [--heartbeat MIN] [--since EPOCH]
       PROFILE may carry variant env like cycle.py: "v7o:THINK_SCHEMA=3;v7o:THINK_SCHEMA=4" (one watchdog per cycle;
       alerts name the variant, and a variant whose logged env lacks its settings is fatal)
exit 2 = fatal, the evaluation was stopped;  1 = alert, still running;  0 = finished or heartbeat.
Alerts already reported are remembered in runs/.watchdog-PROFILE.json, so a restarted watchdog only reports new ones.
"""
import argparse, collections, glob, hashlib, json, os, shutil, signal, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.environ.get("LANES", "http://127.0.0.1:8185,http://127.0.0.1:8186,http://127.0.0.1:8187").split(",")
ERR_KEYS = ("finish_check_error", "audit_error", "reqs_error", "stage_error")
SLOW = 2400          # seconds for one task; the slowest v7x tasks take ~2000 s
STUCK = 20           # this many judgments with one key and one identical p = a stuck judge


def procs(prof):
    """pids of evalmulti.py / eval.py running PROFILE (read from /proc, never pkill -f)"""
    out = []
    for p in os.listdir("/proc"):
        if not p.isdigit():
            continue
        try:
            a = open(f"/proc/{p}/cmdline").read().split("\0")
        except OSError:
            continue
        if len(a) > 2 and any(x.endswith(("evalmulti.py", "eval.py")) for x in a[1:3]) and set(prof) & set(a[1:4]):
            out.append(int(p))
    return out


def stop(prof, specs=()):
    """stop the cycle that runs these specs (cycle.py stops its own jobs); only without one, every job of the profile"""
    cyc = []
    for p in os.listdir("/proc"):
        try:
            a = open(f"/proc/{p}/cmdline").read().split("\0") if p.isdigit() else []
        except OSError:
            continue
        if len(a) > 2 and a[1].endswith("cycle.py") and specs and all(any(sp in x for x in a[2:4]) for sp in specs):
            cyc.append(int(p))
    for p in cyc or procs(prof):
        try:
            os.kill(p, signal.SIGTERM)   # eval.py removes its sandbox containers on SIGTERM
        except OSError:
            pass


def health(url):
    try:
        with urllib.request.urlopen(url.rstrip("/") + "/health", timeout=10) as r:
            return r.status == 200
    except Exception:
        return False


def read_jsonl(path):
    out = []
    try:
        for l in open(path, errors="replace"):
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("profile")
    ap.add_argument("--expect", default="")
    ap.add_argument("--out", default=None)
    ap.add_argument("--heartbeat", type=float, default=30)
    ap.add_argument("--since", type=float, default=None)
    ap.add_argument("--slow", type=float, default=SLOW, help="seconds per task before an alert (raise it while other jobs share the servers)")
    ap.add_argument("--min-tps", type=float, default=12, help="output tok/s of the last 8 model calls below which a lane counts as overloaded")
    ap.add_argument("--jev", default=os.path.join(HERE, "runs", "jev.jsonl"), help="judgment log (tests use their own file)")
    a = ap.parse_args()
    specs = [x for x in a.profile.split(";") if x]
    names = sorted({x.split(":", 1)[0] for x in specs})
    prof = names
    want = {x: dict(kv.split("=", 1) for kv in x.partition(":")[2].split(",") if kv) for x in specs}

    def variant(L):
        """the spec a log belongs to: the one whose env settings the log's env has (most settings first)"""
        h = next((d for d in L if "feats" in d), {})
        env = h.get("env") or {}
        for sp in sorted(specs, key=lambda x: -len(want[x])):
            if sp.split(":", 1)[0] == h.get("profile") and all(env.get(k) == v for k, v in want[sp].items()):
                return sp, h
        return None, h
    expect = {x for x in a.expect.split(",") if x}
    statef = os.path.join(HERE, "runs", ".watchdog-" + "+".join(names) + ".json")
    st = json.load(open(statef)) if os.path.exists(statef) else {}
    since = a.since or st.get("since") or time.time() - 60
    seen = set(st.get("seen", []))
    t_start, bad_health = time.time(), collections.Counter()

    def save():
        json.dump({"since": since, "seen": sorted(seen)}, open(statef, "w"))

    def report(level, msg, key=None):
        key = key or msg
        if key in seen:
            return
        seen.add(key)
        save()
        if level == "fatal":
            stop(prof, specs)
            print(f"FATAL (evaluation stopped): {msg}", flush=True)
            sys.exit(2)
        print(f"ALERT: {msg}", flush=True)
        sys.exit(1)

    save()
    while True:
        logs = [f for n in names for f in glob.glob(os.path.join(HERE, "runs", f"{n}-*", "*", "log.jsonl")) if os.path.getmtime(f) >= since]
        code_now = hashlib.sha1(open(os.path.join(HERE, "agent_v5.py"), "rb").read()).hexdigest()[:8]
        old_code = []
        for f in logs:
            L = read_jsonl(f)
            sp, h = variant(L)
            if h and "env" in h and sp is None and len(specs) > 1:
                # another run of the same profile (10-24: a stop test's log matched no variant and this was fatal; the
                # stop took the whole cycle down): not ours, skip it
                continue
            task = f"{sp or h.get('profile', '?')} {f.split('/')[-2]}"
            if h.get("code") and h["code"] != code_now and not any("result" in d for d in L):
                old_code.append(task)
            feats = next((d["feats"] for d in L if "feats" in d), None)
            if feats is not None and expect - set(feats):
                report("fatal", f"{task}: profile {prof} lacks features {sorted(expect - set(feats))} (name collision?)", f"feats:{prof}")
            for d in L:
                for k in ERR_KEYS:
                    if k in d:
                        report("alert", f"{task}: {k}: {str(d[k])[:300]}", f"{f}:{k}:{str(d[k])[:80]}")
            res = next((d["result"] for d in L if "result" in d), None)
            if res and res.get("error"):
                report("alert", f"{task}: crashed: {res['error'][:300]}", f"{f}:crash")
            calls = [json.dumps(d["calls"]) for d in L if "calls" in d]
            top = collections.Counter(calls[-8:]).most_common(1)
            if not res and top and top[0][1] >= 5:
                report("alert", f"{task}: same call {top[0][1]}x in the last 8 steps (step {len(calls)}): {top[0][0][:200]}",
                       f"{f}:loop")  # once per task: the same known loop re-alerted every 8 steps
            # 10-24: problems that ran unseen for a whole cycle
            for d in L:
                th = " ".join(c[1] for c in d.get("calls") or [] if c[0] == "think")
                if "typed think failed" in th:
                    report("alert", f"{task}: typed think failed: {th[:200]}", f"{f}:typedfail")
            if res is None and any(d.get("deadline") for d in L) \
                    and time.time() - os.path.getmtime(f) > 120:
                report("alert", f"{task}: deadline passed but no result for 2 min (hung finish check?)", f"{f}:hung")
            # slow = low output speed, not long steps: a 2400-token write_file at a normal ~47 tok/s takes 51 s (10-24)
            st_ = [d for d in L if "llm_s" in d and d.get("tok")]
            # a fused [think, action] step logs only the action's tokens (the typed think's are not counted), so it
            # looks slow (cycle 27: 12 tok/s with lanes at ~105 tok/s for 4 requests); speed is taken without those
            sp_ = [d for d in st_ if not (d["calls"] and d["calls"][0][0] == "think" and len(d["calls"]) > 1)]
            if len(sp_) >= 8:
                tps = sum(d["tok"] for d in sp_[-8:]) / max(sum(d["llm_s"] for d in sp_[-8:]), 1)
                if tps < a.min_tps and sum(d["llm_s"] for d in sp_[-8:]) > 120:
                    report("alert", f"{task}: last 8 model calls ran at {tps:.0f} tok/s (overloaded lane?)", f"{f}:slowsteps")
            for d in st_:
                if d["tok"] >= 3000 and not d["calls"]:
                    report("alert", f"{task}: step {d['step']}: {d['tok']} tokens and no tool call (runaway output, {d['llm_s']} s)",
                           f"{f}:runaway")
                if d["tok"] >= 4090 and d["calls"]:  # without a call it is already reported as runaway
                    report("alert", f"{task}: step {d['step']}: reply hit max_tokens ({d['tok']}): {[c[0] for c in d['calls']]}",
                           f"{f}:maxtok")
            age = time.time() - os.path.getctime(os.path.dirname(f))   # the task dir is made at the start; the log's ctime moves with every write
            live = time.time() - os.path.getmtime(f) < 600   # a killed run leaves a log without result forever
            if not res and live and age > a.slow:
                report("alert", f"{task}: running {int(age)} s (step {len(calls)})", f"{f}:slow")
        # judgments: one key with the same p again and again is a broken reading, not a decision
        J = [d for d in read_jsonl(a.jev) if d.get("t", 0) >= since]
        # a broken reading shows as a probability that disagrees with the value the model wrote (10-23: the "ted" of
        # the key "violated" was read as true, so p=1.0 while the answer was false). Long runs of one value are normal
        # (a correct result gives 60 x violated=0, consistent=1), so they are only reported, never fatal.
        by = collections.defaultdict(list)
        for d in J:
            by[d["key"]].append(d)
        for k, ds in by.items():
            rec = [d for d in ds if d.get("val") in (True, False)][-STUCK:]
            off = sum((d["p"] >= 0.5) != d["val"] for d in rec)
            if len(rec) >= 10 and off >= len(rec) // 2:
                report("fatal", f"judge key '{k}': probability disagrees with the written answer in {off} of the last {len(rec)} calls (broken reading)", f"stuck:{k}:{len(ds) // STUCK}")
            # (a run of one value is not reported: 50 items x several correct results gave 300 x consistent=1.0)
        for u in LANES:
            bad_health[u] = 0 if health(u) else bad_health[u] + 1
            if bad_health[u] >= 3:
                report("fatal", f"server {u} is not answering /health", f"health:{u}:{int(time.time() // 600)}")
        if shutil.disk_usage(HERE).free < 5e9:
            report("alert", f"disk almost full: {shutil.disk_usage(HERE).free / 1e9:.1f} GB free", f"disk:{int(time.time() // 3600)}")
        out = open(a.out).read() if a.out and os.path.exists(a.out) else ""
        for l in out.splitlines():
            if " ERROR " in l and l.split() and l.split()[0].split(":", 1)[0] in names:
                report("alert", f"job ended without a result (hard-stopped or crashed): {l.strip()[:200]}", f"err:{l.strip()[:80]}")
        if "\n== " in "\n" + out:
            print("FINISHED\n" + out, flush=True)
            sys.exit(0)
        if not procs(prof) and time.time() - t_start > 120:
            print("FINISHED (no process left)\n" + out, flush=True)
            sys.exit(0)
        if time.time() - t_start > a.heartbeat * 60:
            done = out.count(" steps=")
            print(f"HEARTBEAT: {done} task(s) done, {len(logs)} log(s), {len(J)} judgments, no new problem"
                  + (f"; still on code from before the last agent_v5.py change: {old_code}" if old_code else "")
                  + "\n" + out[-1500:], flush=True)
            sys.exit(0)
        time.sleep(20)


if __name__ == "__main__":
    main()
