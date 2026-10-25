#!/bin/bash
# graded copy of tasks_v8/z_settings_migrate (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || guard_fail "tests/test_cli.py was modified"
test ! -e tool/legacy_settings.py; chk $? "tool/legacy_settings.py still exists"
if grep -rl --include='*.py' legacy_settings . ; then chk 1 "files above still mention legacy_settings"; else chk 0; fi
test -f tool/settings.py; chk $? "tool/settings.py missing"
items 9 15 python3 /check/utrun.py --suite test_cli=8
items 53 12 python3 /check/check_settings.py /work
finish
