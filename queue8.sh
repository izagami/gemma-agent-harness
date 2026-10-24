#!/bin/sh
# v8 held-out suite, Gemma 4 26B: 2x2 of {bare, v7e harness} x {no playbook, playbook}, 80 steps each, 3 lanes
cd ~/llm/local-agent
export TASKS_DIR=$PWD/tasks_v8 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
for p in v080 v0pb80 v7e v7p; do python3 -u evalmulti.py $p > eval-v8-$p.out 2>&1; done
echo QUEUEDONE >> eval-v8-v7p.out
