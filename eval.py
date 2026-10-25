#!/usr/bin/env python3
"""Run the task suite with one harness profile. usage: eval.py PROFILE [task ...]
Writes runs/<profile>-<time>/<task>/{work/, log.jsonl} and results.jsonl."""
import hashlib, re, json, os, shutil, signal, subprocess, sys, time
import agent

def _killed(*_):
    """A killed run must still remove its sandbox containers (22 were left behind on 10-22). Tasks run in worker
    threads, so raising SystemExit here only stopped the main thread and the process kept running: clean up, exit now."""
    for name in list(agent.LIVE):
        subprocess.run(["podman", "rm", "-f", "-t", "0", name], capture_output=True)
    os._exit(143)


signal.signal(signal.SIGTERM, _killed)

HERE = os.path.dirname(os.path.abspath(__file__))
TASKS_DIR = os.environ.get("TASKS_DIR", os.path.join(HERE, "tasks"))


def sandbox_conf(taskdir):
    """sandbox.json in a task dir: {"image": ..., "mounts": ["{HERE}/cad:/opt/cad:ro,Z", ...]} (optional)."""
    p = os.path.join(taskdir, "sandbox.json")
    if not os.path.exists(p):
        return None, []
    d = json.load(open(p))
    return d.get("image"), [m.replace("{HERE}", HERE) for m in d.get("mounts", [])]


def check(workdir, checkdir):
    image, mounts = sandbox_conf(os.path.dirname(checkdir))
    r = subprocess.run(["podman", "run", "--rm", "--network", "none", "--userns=keep-id",
                        "-v", f"{workdir}:/work:Z", "-v", f"{checkdir}:/check:ro,Z", *[a for m in mounts for a in ("-v", m)],
                        image or agent.IMAGE,
                        "timeout", "60", "bash", "/check/check.sh"], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def main():
    argv = sys.argv[1:]
    jobs = 1
    if argv and argv[0].startswith("-j"):
        jobs = int(argv.pop(0)[2:])
    prof = argv[0]
    tasks = argv[1:] or sorted(os.listdir(TASKS_DIR))
    run = os.path.join(HERE, "runs", f"{prof}-{time.strftime('%m%d-%H%M%S')}-{os.getpid()}")
    os.makedirs(run)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock()
    passed = [0]

    def one(tid):
        src = os.path.join(TASKS_DIR, tid)
        work = os.path.join(run, tid, "work")
        if os.path.isdir(os.path.join(src, "files")):
            shutil.copytree(os.path.join(src, "files"), work)
        else:
            os.makedirs(work)
        task_text = open(os.path.join(src, "task.md")).read()
        image, mounts = sandbox_conf(src)
        if image:
            agent.SANDBOX_FOR[os.path.join(run, tid)] = (image, mounts)
        logf = open(os.path.join(run, tid, "log.jsonl"), "w")
        def log(d):
            logf.write(json.dumps(d, ensure_ascii=False) + "\n"); logf.flush()
        if prof.startswith(("v5", "v6", "v7", "v8", "v9")):
            import agent_v5
            # the variant env and the code version, so a watchdog can tell variants of one profile apart and see which
            # jobs started before a mid-cycle fix (10-24)
            log({"profile": prof, "feats": sorted(agent_v5.feats(prof)),
                 "env": {k: os.environ[k] for k in sorted(os.environ) if re.fullmatch(r"(THINK|CONTENT|EV|AGENT_TEMP|EDIT\d*|MIDGATE|FEATS_OFF|FINISH_NUDGE|KNOW|LINT|VBC|KIT|VISION|PWKIT|KNOW2|FIX73|SKILLS|KITTEST|TIMEAWARE|EDGEPASS)(_[A-Z_]+)?", k)},
                 "code": hashlib.sha1(open(agent_v5.__file__, "rb").read()).hexdigest()[:8]})
        try:
            if prof.startswith("g"):
                import agent_g
                info = agent_g.run_task(task_text, work, prof, log)
            elif prof.startswith(("v5", "v6", "v7", "v8", "v9")):
                import agent_v5
                info = agent_v5.run_task(task_text, work, prof, log)
            else:
                info = agent.run_task(task_text, work, prof, log)
        except Exception as e:
            import traceback
            info = {"error": repr(e), "trace": traceback.format_exc()[-1500:]}
        ok, out = check(work, os.path.join(src, "check"))
        # graded hidden checks (tasks_qg) print "SCORE k/n"; without one the score is the verdict (1 or 0)
        sm = re.findall(r"^SCORE (\d+)/(\d+)", out, re.M)
        score = int(sm[-1][0]) / int(sm[-1][1]) if sm and int(sm[-1][1]) else float(ok)
        score = min(score, 0.999) if not ok else score   # a failed result never rounds up to a full score
        res = {"task": tid, "pass": ok, "score": round(score, 4), **info, "check_out": out[-300:]}
        log({"result": res}); logf.close()
        with lock:
            passed[0] += ok
            with open(os.path.join(run, "results.jsonl"), "a") as f:
                f.write(json.dumps(res, ensure_ascii=False) + "\n")
            print(f"{tid:12s} {'PASS' if ok else 'fail'} steps={info.get('steps')} t={info.get('seconds')} {info.get('error', '')}", flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(jobs) as ex:
        list(ex.map(one, tasks))
    print(f"== {prof}: {passed[0]}/{len(tasks)} passed in {round(time.time() - t0)} s  ({run})", flush=True)


if __name__ == "__main__":
    main()
