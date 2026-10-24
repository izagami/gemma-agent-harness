#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/make_v1.py /check/orig_make_v1.py || { echo "data/make_v1.py was modified"; exit 1; }
cmp -s tests/test_migrate.py /check/orig_test_migrate.py || { echo "tests/test_migrate.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q 2>&1 | tail -15; [ ${PIPESTATUS[0]} -eq 0 ] || UT=1   # stdout and short: the SCORE line must stay in the last 1500 chars
python3 /check/check_migrate.py || HC=1
exit $(( ${UT:-0} | ${HC:-0} ))
