#!/bin/sh
# after v7s: v7t (typed notes: choices + one sentence)
cd ~/llm/local-agent
while ps -eo args | grep -q "^python3 -u evalmulti.py v7s$"; do sleep 30; done
export TASKS_DIR=$PWD/tasks_v8 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
python3 -u evalmulti.py v7t > eval-v8-v7t.out 2>&1
