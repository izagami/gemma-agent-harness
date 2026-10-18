#!/bin/bash
cd ~/llm/local-agent
until grep -q '== v2' eval-run2.out; do sleep 20; done
python3 -u eval.py v3
