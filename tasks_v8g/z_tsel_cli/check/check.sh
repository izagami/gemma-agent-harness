#!/bin/bash
# graded copy of tasks_v8/z_tsel_cli (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
test -f tsel.py; chk $? "tsel.py missing"
test -f tests/test_tsel.py; chk $? "tests/test_tsel.py missing"
for f in samples/people.tsv samples/orders.csv; do cmp -s $f /check/$(basename $f) || guard_fail "$f was modified"; done
items 51 12 python3 /check/check_tsel.py
items 1 15 python3 /check/utrun.py --suite
n=$(timeout "$(left)" python3 -c "import unittest; print(unittest.defaultTestLoader.discover('tests', pattern='test_tsel.py').countTestCases())")
echo "tests in tests/test_tsel.py: $n"
test -n "$n" && test "$n" -ge 8; chk $? "only $n tests in tests/test_tsel.py"
finish
