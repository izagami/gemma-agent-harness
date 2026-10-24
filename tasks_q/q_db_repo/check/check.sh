#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/schema.sql /check/orig_schema.sql || { echo "data/schema.sql was modified"; exit 1; }
cmp -s data/make_db.py /check/orig_make_db.py || { echo "data/make_db.py was modified"; exit 1; }
cmp -s tests/test_repo.py /check/orig_test_repo.py || { echo "tests/test_repo.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_repo.py
