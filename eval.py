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
    prof = sys.argv[1]
    tasks = sys.argv[2:] or sorted(os.listdir(os.path.join(HERE, "tasks")))
    run = os.path.join(HERE, "runs", f"{prof}-{time.strftime('%m%d-%H%M%S')}")
    os.makedirs(run)
    passed = 0
    for tid in tasks:
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
            info = agent.run_task(task_text, work, prof, log)
        except Exception as e:
            info = {"error": repr(e)}
        ok, out = check(work, os.path.join(src, "check"))
        passed += ok
        res = {"task": tid, "pass": ok, **info, "check_out": out[-300:]}
        log({"result": res}); logf.close()
        with open(os.path.join(run, "results.jsonl"), "a") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"{tid:12s} {'PASS' if ok else 'fail'} steps={info.get('steps')} t={info.get('seconds')} {info.get('error', '')}", flush=True)
    print(f"== {prof}: {passed}/{len(tasks)} passed  ({run})", flush=True)


if __name__ == "__main__":
    main()
