#!/bin/bash
# graded copy of tasks_v8/z_migrations (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || guard_fail "tests/test_cli.py was modified"
cmp -s migrations/001_initial.sql /check/001_initial.sql || guard_fail "migrations/001_initial.sql was modified"
cmp -s migrations/002_add_pinned.sql /check/002_add_pinned.sql || guard_fail "migrations/002_add_pinned.sql was modified"
items 7 15 python3 /check/utrun.py --suite test_cli=6
items 54 12 python3 /check/check_mig.py /work
finish
