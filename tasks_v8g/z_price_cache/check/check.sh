#!/bin/bash
# graded copy of tasks_v8/z_price_cache (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
for f in catalog.json prices_v2.json customers.json may01.jsonl; do cmp -s data/$f /check/orig_$f || guard_fail "data/$f was modified"; done
for f in test_rules.py test_pricing.py test_report.py; do cmp -s tests/$f /check/orig_$f || guard_fail "tests/$f was modified"; done
items 10 15 python3 /check/utrun.py --suite test_rules=3 test_pricing=4 test_report=2
items 21 12 python3 /check/check_pricing.py
finish
