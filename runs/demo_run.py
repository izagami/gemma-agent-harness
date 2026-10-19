"""Run the CAD agent (v8c) on runs/<dir>/task.md; log to runs/<dir>/log.jsonl, files in runs/<dir>/work."""
import json, os, sys
sys.path.insert(0, os.path.expanduser("~/llm/local-agent"))
import agent_v5
d = os.path.abspath(sys.argv[1]); w = os.path.join(d, "work"); os.makedirs(w, exist_ok=True)
log = open(os.path.join(d, "log.jsonl"), "w")
def emit(e):
    log.write(json.dumps(e, ensure_ascii=False) + "\n"); log.flush()
info = agent_v5.run_task(open(os.path.join(d, "task.md")).read(), w, "v8c", emit)
emit({"result": {k: info[k] for k in ("steps", "finished", "seconds")}})
print(json.dumps({k: info[k] for k in ("steps", "finished", "seconds")}))
