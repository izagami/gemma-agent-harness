#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/releases.txt /check/orig_releases.txt || { echo "data/releases.txt was modified"; exit 1; }
cmp -s tests/test_vsort.py /check/orig_test_vsort.py || { echo "tests/test_vsort.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_semver.py
