#!/bin/bash
# graded copy of tasks_v8/z_billing_periods (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
for f in test_dates.py test_invoice.py; do cmp -s tests/$f /check/$f || guard_fail "tests/$f was modified"; done
cmp -s docs/FORMAT.md /check/FORMAT.md || guard_fail "docs/FORMAT.md was modified"
for f in plans.csv subscriptions.csv; do cmp -s data/$f /check/$f || guard_fail "data/$f was modified"; done
export PYTHONDONTWRITEBYTECODE=1
items 9 15 python3 /check/utrun.py --suite test_dates=4 test_invoice=4
items 19 12 python3 /check/check_billing.py
finish
