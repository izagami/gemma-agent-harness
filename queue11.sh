#!/bin/sh
# full v8 suite with the unified harness once the single-task v8u tests are done
cd ~/llm/local-agent
while ps -eo args | grep -q "[e]val.py v8u"; do sleep 30; done
export TASKS_DIR=$PWD/tasks_v8 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
python3 -u evalmulti.py v8u > eval-v8-v8u.out 2>&1
