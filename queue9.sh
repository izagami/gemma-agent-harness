#!/bin/sh
# after the spec_test-fixed v7e run: v7s (forced notes before every action)
cd ~/llm/local-agent
while ps -eo args | grep -q "^python3 -u evalmulti.py v7e$"; do sleep 30; done
export TASKS_DIR=$PWD/tasks_v8 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087
python3 -u evalmulti.py v7s > eval-v8-v7s.out 2>&1
