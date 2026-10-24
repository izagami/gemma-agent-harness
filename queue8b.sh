#!/bin/sh
# after queue8 (v7e, v7p): rerun the bare pair with nudge-on-no-call (Gemma 4 26B often stops with a stray <tool_call|>)
cd ~/llm/local-agent
until grep -q QUEUEDONE eval-v8-v7p.out 2>/dev/null; do sleep 30; done
export TASKS_DIR=$PWD/tasks_v8 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
for p in v080 v0pb80; do python3 -u evalmulti.py $p > eval-v8-$p.out 2>&1; done
echo QUEUEDONE >> eval-v8-v0pb80.out
