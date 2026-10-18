#!/bin/bash
cd ~/llm/local-agent
until grep -q '^== v7d' eval-v7d.out; do sleep 30; done
python3 -u evalmulti.py v7e > eval-v7e.out 2>&1
