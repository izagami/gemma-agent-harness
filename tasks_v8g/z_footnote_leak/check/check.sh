#!/bin/bash
# graded copy of tasks_v8/z_footnote_leak (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_render.py /check/test_render.py || guard_fail "tests/test_render.py was modified"
cmp -s tests/onboarding.html /check/onboarding.html || guard_fail "tests/onboarding.html was modified"
cmp -s docs/SYNTAX.md /check/SYNTAX.md || guard_fail "docs/SYNTAX.md was modified"
for n in onboarding release style; do cmp -s examples/$n.txt /check/examples/$n.txt || guard_fail "examples/$n.txt was modified"; done
items 5 15 python3 /check/utrun.py --suite test_render=4
items 35 12 python3 /check/check_render.py
finish
