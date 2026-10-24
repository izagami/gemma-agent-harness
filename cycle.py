#!/usr/bin/env python3
"""10-minute improvement cycle: two profiles on the same tasks at the same time, paired, under the same load.

usage: cycle.py BASE CAND[;CAND2;...] [task ...]   (a candidate may carry env: "v7a:THINK_ABORT=600,X=1")     (default tasks: alternating halves of HOT, the q25 tasks whose result varied
       between full runs; with several candidates all of HOT, so the 12 slots stay full: 10-24 cycle 10 used only 55% of
       its job-slot time, as early finishers left slots idle until the slowest job ended)
env:   LANES (vLLM lanes), PER_LANE (jobs per lane, default 4), STEP_CAP (default 80: only the deadline cuts, so a faster harness gets more steps), TASK_DEADLINE (default 540 s),
       CAND_ENV="K=V K2=V2" (extra env for the candidate only, e.g. EV_DIFFLINE=1), REPS (runs per task and profile, 1)
Each task's hidden check judges the state reached at the cap/deadline. Prints a paired table and wins/losses, and
appends a summary line to runs/cycles.jsonl. Full 80-step runs (run_vllm.sh) stay the adoption test.
"""
import json, os, queue, signal, subprocess, sys, threading, time

HERE = os.path.dirname(os.path.abspath(__file__))
LANES = os.environ.get("LANES", "http://127.0.0.1:8185,http://127.0.0.1:8186,http://127.0.0.1:8187").split(",")
# q25 tasks that both passed and failed across the v7x/v7q/v7r full runs of 10-23: they carry the signal
HOT = ["q_browser_export", "q_browser_fix", "q_cad_wheel", "q_db_migrate", "q_db_repo", "q_lru_ttl", "q_toposort",
       "q_sec_firewall", "q_csv_merge", "q_semver_sort", "q_tax_round", "q_three_fix"]


def main():
    base, cands, tasks = sys.argv[1], sys.argv[2].split(";"), sys.argv[3:]
    cand = cands[0]
    if not tasks and len(cands) > 1:
        tasks = HOT
    if not tasks:
        # half of HOT per cycle, alternating: 12 jobs = 4 per card, the most a card decodes fastest at with 15-20K-token
        # contexts (10-23: 178 tok/s total at 4 streams, 133 at 8); two cycles in a row cover all 12 tasks
        try:
            done = sum(1 for l in open(os.path.join(HERE, "runs", "cycles.jsonl"))
                       if (lambda d: d["base"] == base and d["cand"] == cand)(json.loads(l)))
        except OSError:
            done = 0
        tasks = HOT[done % 2::2]
    reps = int(os.environ.get("REPS", "1"))
    cand_env = dict(kv.split("=", 1) for kv in os.environ.get("CAND_ENV", "").split())
    # tasks_qg: tasks_q with graded hidden checks (SCORE k/n, same verdicts; 10-24)
    common = {"TASKS_DIR": os.environ.get("TASKS_DIR", os.path.join(HERE, "tasks_qg")), "AGENT_MODEL": "gemma4",
              "STEP_CAP": os.environ.get("STEP_CAP", "80"), "TASK_DEADLINE": os.environ.get("TASK_DEADLINE", "540"),
              "JEV_WORKERS": os.environ.get("JEV_WORKERS", "3")}
    # interleave the two profiles so both see the same load all the way through
    q = queue.Queue()
    for r in range(reps):
        for t in tasks:
            for prof in [base] + cands:
                q.put((prof, t, r))
    res, lock, t0 = {}, threading.Lock(), time.time()
    live = set()

    stopping = []

    def stop(*_):
        stopping.append(1)  # lanes take no new job from here on
        # 10-24: killing cycle.py alone left its eval.py jobs running (23 jobs on the cards at once, and a later sandbox
        # sweep removed a running job's container); stopping the cycle stops its jobs, whose handlers remove sandboxes
        for pr in list(live):
            pr.terminate()
        for pr in list(live):
            try:
                pr.wait(timeout=60)
            except subprocess.TimeoutExpired:
                pr.kill()
        os._exit(1)
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def lane(url):
        while not stopping:
            try:
                prof, t, r = q.get_nowait()
            except queue.Empty:
                return
            env = dict(os.environ, **common, AGENT_API=url.rstrip("/") + "/v1/chat/completions", LANES=url)
            if prof != base:
                env.update(cand_env)
            # "v7a:THINK_ABORT=600" = profile v7a with extra env, compared as its own candidate
            name, _, kv = prof.partition(":")
            env.update(dict(x.split("=", 1) for x in kv.split(",") if x))
            # hard stop: the deadline is checked only between steps (10-24 db_repo ran 687 s against 540). SIGTERM, not
            # SIGKILL, so eval.py's handler removes its sandbox containers
            pr = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "eval.py"), name, t], env=env,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            live.add(pr)
            if stopping:  # started while stop() was running
                pr.terminate()
            try:
                out, _ = pr.communicate(timeout=int(common["TASK_DEADLINE"]) + 240)  # browser tasks: finish gate + hidden check took >90 s
            except subprocess.TimeoutExpired:
                pr.terminate()
                out, _ = pr.communicate()
            live.discard(pr)
            p = subprocess.CompletedProcess(pr.args, pr.returncode, out, "")
            line = [l for l in p.stdout.splitlines() if l.startswith("== ")]
            d = line[-1].rsplit("(", 1)[-1].rstrip(")") if line else None
            ok = None
            if d and os.path.exists(os.path.join(d, "results.jsonl")):
                rr = json.loads(open(os.path.join(d, "results.jsonl")).read().splitlines()[0])
                ok = (rr["pass"], rr.get("steps"), rr.get("seconds"), d, rr.get("score", float(rr["pass"])))
            with lock:
                res[(prof, t, r)] = ok
                print(f"{prof:5s} {t:20s} {'ERROR' if ok is None else ('PASS' if ok[0] else 'fail')} "
                      f"score={ok and round(ok[4], 2)} steps={ok and ok[1]} t={ok and ok[2]}  [{round(time.time() - t0)} s]", flush=True)

    per = int(os.environ.get("PER_LANE", "4"))
    th = [threading.Thread(target=lane, args=(u,)) for u in LANES for _ in range(per)]
    [x.start() for x in th]; [x.join() for x in th]
    wall = round(time.time() - t0)
    n = len(tasks) * reps
    used = sum(v[2] or 0 for v in res.values() if v)
    nb = sum(1 for k, v in res.items() if k[0] == base and v and v[0])
    for cand in cands:
        nc = sum(1 for k, v in res.items() if k[0] == cand and v and v[0])
        wins = [t for t in tasks for r in range(reps) if (res.get((cand, t, r)) or [0])[0] and not (res.get((base, t, r)) or [0])[0]]
        loss = [t for t in tasks for r in range(reps) if (res.get((base, t, r)) or [0])[0] and not (res.get((cand, t, r)) or [0])[0]]
        # graded score (tasks_qg): mean per profile and the paired mean difference, a finer signal than pass counts
        sb = [(res.get((base, t, r)) or [0, 0, 0, 0, 0])[4] for t in tasks for r in range(reps)]
        sc_ = [(res.get((cand, t, r)) or [0, 0, 0, 0, 0])[4] for t in tasks for r in range(reps)]
        dif = [b - a for a, b in zip(sb, sc_)]
        print(f"== cycle {base} {nb}/{n} vs {cand} {nc}/{n}  wins {wins}  losses {loss}  in {wall} s", flush=True)
        print(f"   score {sum(sb) / n:.3f} vs {sum(sc_) / n:.3f}  paired diff {sum(dif) / n:+.3f} "
              f"(better on {sum(d > 0.001 for d in dif)}, worse on {sum(d < -0.001 for d in dif)})", flush=True)
        open(os.path.join(HERE, "runs", "cycles.jsonl"), "a").write(json.dumps(
            {"time": time.strftime("%m-%d %H:%M"), "base": base, "cand": cand, "cand_env": cand_env, "tasks": tasks,
             "reps": reps, "base_pass": nb, "cand_pass": nc, "wins": wins, "losses": loss, "seconds": wall,
             "base_score": round(sum(sb) / n, 4), "cand_score": round(sum(sc_) / n, 4),
             "step_cap": common["STEP_CAP"], "deadline": common["TASK_DEADLINE"]}) + "\n")
    print(f"slot use {round(100 * used / (len(th) * wall))}% of {len(th)} slots", flush=True)
    # a job stopped at the hard deadline can leave its sandbox (10-24: 12 left after a stopped run); this cycle's jobs
    # are all done here, so every per-task sandbox (agent-<8 hex>) still present is a leftover
    names = subprocess.run(["podman", "ps", "-a", "--format", "{{.Names}}"], capture_output=True, text=True).stdout.split()
    left = [n for n in names if len(n) == 14 and n.startswith("agent-") and all(ch in "0123456789abcdef" for ch in n[6:])]
    if left:
        subprocess.run(["podman", "rm", "-f", *left], capture_output=True)
        print(f"removed {len(left)} leftover sandboxes", flush=True)

if __name__ == "__main__":
    main()
