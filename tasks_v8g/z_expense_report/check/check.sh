#!/bin/bash
# graded copy of tasks_v8/z_expense_report (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || guard_fail "tests/test_cli.py was modified"
for f in rates.json sample.csv; do cmp -s data/$f /check/$f || guard_fail "data/$f was modified"; done
test -f tests/test_report.py; chk $? "tests/test_report.py missing"
items 5 15 python3 /check/utrun.py --suite test_cli=4
n=$(timeout "$(left)" python3 -c "import unittest; print(unittest.defaultTestLoader.discover('tests', pattern='test_report.py').countTestCases())")
test -n "$n" && test "$n" -ge 3; chk $? "only $n tests in tests/test_report.py"
items 29 12 python3 /check/check_report.py
finish
