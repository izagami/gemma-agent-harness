#!/bin/bash
# graded copy of tasks_v8/z_vendor_import (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
for f in vendor_a.csv vendor_b.csv vendor_c.csv; do cmp -s data/$f /check/orig_$f || guard_fail "data/$f was modified"; done
for f in test_sniff.py test_normalize.py test_store.py; do cmp -s tests/$f /check/orig_$f || guard_fail "tests/$f was modified"; done
items 11 15 python3 /check/utrun.py --suite test_sniff=3 test_normalize=4 test_store=3
items 11 12 python3 /check/check_import.py
finish
