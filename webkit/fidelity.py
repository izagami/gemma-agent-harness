#!/usr/bin/env python3
"""fidelity.py TASK_MD PNG [PNG ...]: does each screenshot show what the task asks for? (vision model judge)

1. the model lists the concrete things the task names (e.g. "medieval stone castle", "market town")
2. for every screenshot and every thing: a boolean judgment on the image, JSON-schema constrained, with the
   probability of the answer from the token logprobs (fast typed judgment, like agent_g.judge)
Prints one line per screenshot: fidelity = mean probability that each thing is present.
Needs a model server with image input (vllm_lane.sh VISION=1). Env: JUDGE_API (default lane 8185).
"""
import base64
import json
import math
import os
import sys
import urllib.request

API = os.environ.get("JUDGE_API", "http://127.0.0.1:8185/v1/chat/completions")


def call(messages, schema, max_tokens=300):
    body = {"model": "gemma4", "messages": messages, "max_tokens": max_tokens, "temperature": 0, "logprobs": True, "top_logprobs": 5,
            "response_format": {"type": "json_schema", "json_schema": {"name": "a", "schema": schema}}}
    r = json.load(urllib.request.urlopen(urllib.request.Request(API, json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=300))
    return r["choices"][0]


def things(task):
    c = call([{"role": "user", "content": "Task:\n" + task + "\n\nList the concrete things this task asks to be visible in the "
                                          "result (2-5 short noun phrases, e.g. 'stone castle', 'market town', 'boats'). Leave out "
                                          "style words and technical requirements."}],
             {"type": "object", "properties": {"things": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 5}},
              "required": ["things"]})
    ts = json.loads(c["message"]["content"])["things"]
    return [t for t in ts if not any(w in t.lower() for w in ("voxel", "html", "file", "environment", "scene", "art"))] or ts


def present(png, thing):
    img = base64.b64encode(open(png, "rb").read()).decode()
    c = call([{"role": "user", "content": [
        {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img}},
        {"type": "text", "text": f"Is there clearly a {thing} in this picture (recognizable at a glance, not just something vaguely "
                                 f"similar)? Answer present=true only if so."}]}],
        {"type": "object", "properties": {"present": {"type": "boolean"}}, "required": ["present"]}, max_tokens=20)
    val = json.loads(c["message"]["content"])["present"]
    p = None
    for t in (c.get("logprobs") or {}).get("content") or []:
        if t["token"].strip() in ("true", "false"):
            pt = sum(math.exp(x["logprob"]) for x in t["top_logprobs"] if x["token"].strip() == "true")     # " true" and "true"
            pf = sum(math.exp(x["logprob"]) for x in t["top_logprobs"] if x["token"].strip() == "false")
            p = pt / (pt + pf) if pt + pf > 0 else (1.0 if val else 0.0)
            break
    return val, (p if p is not None else (1.0 if val else 0.0))


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    task = open(sys.argv[1], encoding="utf-8").read()
    ts = things(task)
    print("things:", "; ".join(ts))
    for png in sys.argv[2:]:
        res = [(t, *present(png, t)) for t in ts]
        f = sum(p for _, _, p in res) / len(res)
        print(f"{os.path.basename(png)}: fidelity {f:.2f}  " + "  ".join(f"{t}={'Y' if v else 'n'}({p:.2f})" for t, v, p in res))


if __name__ == "__main__":
    main()
