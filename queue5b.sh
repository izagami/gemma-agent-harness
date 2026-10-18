#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v3' eval-v3b.out; do sleep 20; done
AGENT_API=http://127.0.0.1:8087/v1/chat/completions python3 -u eval.py v5b > eval-v5b.out 2>&1
