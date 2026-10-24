#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/make_v1.py /check/orig_make_v1.py || { echo "data/make_v1.py was modified"; exit 1; }
cmp -s tests/test_migrate.py /check/orig_test_migrate.py || { echo "tests/test_migrate.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_migrate.py
