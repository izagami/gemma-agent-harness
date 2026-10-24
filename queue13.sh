#!/bin/bash
# after queue12 (gA on 25): v7x on the 16 non-Python quick tasks, for the same comparison
cd ~/llm/local-agent
while pgrep -f '[q]ueue12.sh' >/dev/null; do sleep 30; done
mkdir -p tasks_q16 && for t in $(ls tasks_q); do [ -e tasks_q9/$t ] || ln -sfn ../tasks_q/$t tasks_q16/$t; done
TASKS_DIR=$PWD/tasks_q16 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087 python3 -u evalmulti.py v7x > eval-q16-v7x.out 2>&1
