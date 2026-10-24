#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/notice.txt /check/orig_notice.txt || { echo "data/notice.txt was modified"; exit 1; }
cmp -s tests/test_wrap.py /check/orig_test_wrap.py || { echo "tests/test_wrap.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_wrap.py
