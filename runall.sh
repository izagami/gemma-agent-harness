#!/bin/bash
# two lanes, one per GPU, one task at a time each
cd ~/llm/local-agent
(AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v3 > eval-v3.out 2>&1; AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v5 > eval-v5.out 2>&1) &
(AGENT_API=http://127.0.0.1:8087/v1/chat/completions python3 -u eval.py v4 > eval-v4.out 2>&1) &
wait
