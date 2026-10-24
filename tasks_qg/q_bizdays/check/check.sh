#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/holidays.txt /check/orig_holidays.txt || { echo "data/holidays.txt was modified"; exit 1; }
cmp -s tests/test_ops.py /check/orig_test_ops.py || { echo "tests/test_ops.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q 2>&1 | tail -15; [ ${PIPESTATUS[0]} -eq 0 ] || UT=1   # stdout and short: the SCORE line must stay in the last 1500 chars
python3 /check/check_bizdays.py || HC=1
exit $(( ${UT:-0} | ${HC:-0} ))
