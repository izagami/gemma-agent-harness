#!/usr/bin/env python3
"""Run the task suite with one harness profile. usage: eval.py PROFILE [task ...]
Writes runs/<profile>-<time>/<task>/{work/, log.jsonl} and results.jsonl."""
import json, os, shutil, subprocess, sys, time
import agent

HERE = os.path.dirname(os.path.abspath(__file__))


def check(workdir, checkdir):
    r = subprocess.run(["podman", "run", "--rm", "--network", "none", "--userns=keep-id",
                        "-v", f"{workdir}:/work:Z", "-v", f"{checkdir}:/check:ro,Z", agent.IMAGE,
                        "timeout", "60", "bash", "/check/check.sh"], capture_output=True, text=True)
    return r.returncode == 0, (r.stdout + r.stderr)[-1500:]


def main():
    argv = sys.argv[1:]
    jobs = 1
    if argv and argv[0].startswith("-j"):
        jobs = int(argv.pop(0)[2:])
    prof = argv[0]
    tasks = argv[1:] or sorted(os.listdir(os.path.join(HERE, "tasks")))
    run = os.path.join(HERE, "runs", f"{prof}-{time.strftime('%m%d-%H%M%S')}")
    os.makedirs(run)
    import threading
    from concurrent.futures import ThreadPoolExecutor
    lock = threading.Lock()
    passed = [0]

    def one(tid):
        src = os.path.join(HERE, "tasks", tid)
        work = os.path.join(run, tid, "work")
        if os.path.isdir(os.path.join(src, "files")):
            shutil.copytree(os.path.join(src, "files"), work)
        else:
            os.makedirs(work)
        task_text = open(os.path.join(src, "task.md")).read()
        logf = open(os.path.join(run, tid, "log.jsonl"), "w")
        def log(d):
            logf.write(json.dumps(d, ensure_ascii=False) + "\n"); logf.flush()
        try:
            if prof.startswith(("v5", "v6")):
                import agent_v5
                info = agent_v5.run_task(task_text, work, prof, log)
            else:
                info = agent.run_task(task_text, work, prof, log)
        except Exception as e:
            import traceback
            info = {"error": repr(e), "trace": traceback.format_exc()[-1500:]}
        ok, out = check(work, os.path.join(src, "check"))
        res = {"task": tid, "pass": ok, **info, "check_out": out[-300:]}
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
