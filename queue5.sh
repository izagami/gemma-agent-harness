#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v3' eval-v3.out; do sleep 20; done
AGENT_API=http://127.0.0.1:8085/v1/chat/completions python3 -u eval.py -j4 v5
