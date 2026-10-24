#!/usr/bin/env python3
"""Jev check that each extracted requirement is really in the task or the docs (the model sometimes invents one, e.g.
'the number of holes must be 4 according to the spec test' for q_cad_ramp_bracket). -> runs/replay/grounded.json"""
import concurrent.futures as cf, json, os
import agent_g as G

HERE = os.path.dirname(os.path.abspath(__file__))
Q = ("Task:\n<task>\n{task}\n</task>\n\nProject documents:\n<docs>\n{docs}\n</docs>\n\nProposed requirement:\n{req}\n\n"
     "Is this a requirement of THIS task, stated in the task or the documents above (in other words, or as a direct "
     "consequence of what they say)? Answer grounded=false if it is not there, adds a detail they do not give, or comes "
     "from an example, sample code or general advice in a tool manual rather than from what this task asks for.")


def docs_of(root):
    return "\n\n".join(f"=== {rel} ===\n{G.read(root, rel, 6000)}" for rel in G.files_of(root)
                       if rel.lower().endswith((".md", ".txt", ".rst")) and rel.lower() != "license"
                       and not rel.startswith(("data/", "out/", "tests/")))[:12000]


def main():
    reqs = json.load(open(os.path.join(HERE, "runs", "replay", "reqs.json")))
    out = {}
    for tid, rs in reqs.items():
        root = os.path.join(HERE, "tasks_q", tid, "files")
        task = open(os.path.join(HERE, "tasks_q", tid, "task.md")).read()
        d = docs_of(root)
        with cf.ThreadPoolExecutor(6) as ex:
            out[tid] = list(ex.map(lambda r: round(G.judge(Q.format(task=task, docs=d, req=r), "grounded"), 3), rs))
        print(tid, sum(p < 0.5 for p in out[tid]), "of", len(rs), "not grounded", flush=True)
    json.dump(out, open(os.path.join(HERE, "runs", "replay", "grounded.json"), "w"))


if __name__ == "__main__":
    main()
