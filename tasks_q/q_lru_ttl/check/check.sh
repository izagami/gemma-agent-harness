#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cache.py /check/orig_test_cache.py || { echo "tests/test_cache.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_cache.py
