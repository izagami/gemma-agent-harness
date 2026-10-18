#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v6' eval-v6.out 2>/dev/null; do sleep 15; done
AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v6b stats_cli h_calc h_access duration h_bank x_shop > eval-v6b-smoke.out 2>&1
