#!/bin/bash
cd ~/llm/local-agent
until grep -q '== v1' eval-run1.out; do sleep 20; done
python3 -u eval.py v0 h_access h_bank h_bizdays h_calc h_clean_csv h_dupes h_ini h_inventory h_lru h_md h_money h_ratelimit h_sqlite h_sync h_todo 
python3 -u eval.py v1 h_access h_bank h_bizdays h_calc h_clean_csv h_dupes h_ini h_inventory h_lru h_md h_money h_ratelimit h_sqlite h_sync h_todo 
python3 -u eval.py v2
