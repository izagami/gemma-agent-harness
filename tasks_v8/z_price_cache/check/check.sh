#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in catalog.json prices_v2.json customers.json may01.jsonl; do cmp -s data/$f /check/orig_$f || { echo "data/$f was modified"; exit 1; }; done
for f in test_rules.py test_pricing.py test_report.py; do cmp -s tests/$f /check/orig_$f || { echo "tests/$f was modified"; exit 1; }; done
python3 -m unittest discover -s tests -q
python3 /check/check_pricing.py
