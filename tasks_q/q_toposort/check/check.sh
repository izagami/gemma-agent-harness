#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/project.deps /check/orig_project.deps || { echo "data/project.deps was modified"; exit 1; }
cmp -s tests/test_order.py /check/orig_test_order.py || { echo "tests/test_order.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_order.py
