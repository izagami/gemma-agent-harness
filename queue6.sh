#!/bin/bash
# after the current runs: v6 vs v5c on all 40 tasks, one GPU each
cd ~/llm/local-agent
until grep -q '^== v5f' eval-v5f-smoke.out 2>/dev/null; do sleep 15; done
AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v6 > eval-v6.out 2>&1 &
until grep -q '^== v5e' eval-v5e.out 2>/dev/null; do sleep 15; done
AGENT_API=http://127.0.0.1:8087/v1/chat/completions python3 -u eval.py v5c > eval-v5c-40.out 2>&1 &
wait
