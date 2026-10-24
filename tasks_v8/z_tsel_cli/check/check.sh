#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
test -f tsel.py || { echo "tsel.py missing"; exit 1; }
test -f tests/test_tsel.py || { echo "tests/test_tsel.py missing"; exit 1; }
for f in samples/people.tsv samples/orders.csv; do cmp -s $f /check/$(basename $f) || { echo "$f was modified"; exit 1; }; done
python3 /check/check_tsel.py
timeout 60 python3 -m unittest discover -s tests -q
n=$(python3 -c "import unittest; print(unittest.defaultTestLoader.discover('tests', pattern='test_tsel.py').countTestCases())")
echo "tests in tests/test_tsel.py: $n"
test "$n" -ge 8 || { echo "only $n tests in tests/test_tsel.py"; exit 1; }
