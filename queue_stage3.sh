#!/bin/bash
# stage 3: full q25 runs one after another (never two at once: the 3 servers take 6 requests in total)
cd ~/llm/local-agent
for i in 1 2 3; do
  TASKS_DIR=$PWD/tasks_q JEV_WORKERS=2 python3 evalmulti.py v7q > eval-q25-v7q-$i.out 2>&1
done
