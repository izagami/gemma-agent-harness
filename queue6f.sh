#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v6d' eval-v6d.out 2>/dev/null; do sleep 15; done
AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py v6f > eval-v6f.out 2>&1
