#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v5c' eval-v5c.out; do sleep 15; done
AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v5d h_todo h_sync log_errors import_fix h_bank stats_cli > eval-v5d-smoke.out 2>&1
