#!/bin/bash
# after the running gA python-9 run: v7x baseline on the same 9, then gA (with coverage) on all 25 quick tasks
cd ~/llm/local-agent
while pgrep -f '[e]val.py -j3 gA q_bizdays' >/dev/null; do sleep 30; done
rm -rf tasks_q && mv tasks_q.next tasks_q
P9="q_bizdays q_csv_merge q_duration q_lru_ttl q_paginate q_semver_sort q_tax_round q_toposort q_wrap_cjk"
mkdir -p tasks_q9 && for t in $P9; do ln -sfn ../tasks_q/$t tasks_q9/$t; done
TASKS_DIR=$PWD/tasks_q9 LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087 python3 -u evalmulti.py v7x > eval-q9-v7x.out 2>&1
LANES=http://127.0.0.1:8085,http://127.0.0.1:8086,http://127.0.0.1:8087 TASKS_DIR=$PWD/tasks_q python3 -u eval.py -j3 gA > eval-q25-gA.out 2>&1
