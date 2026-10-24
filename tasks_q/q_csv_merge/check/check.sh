#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in crm.csv shop.csv; do cmp -s data/$f /check/orig_$f || { echo "data/$f was modified"; exit 1; }; done
cmp -s tests/test_merge.py /check/orig_test_merge.py || { echo "tests/test_merge.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_merge.py
