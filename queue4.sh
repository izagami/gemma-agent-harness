#!/bin/bash
cd ~/llm/local-agent
until grep -q '== v3' eval-run3.out; do sleep 20; done
python3 -u eval.py v4
