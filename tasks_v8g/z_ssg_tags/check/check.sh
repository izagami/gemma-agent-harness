#!/bin/bash
# graded copy of tasks_v8/z_ssg_tags (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
for f in base.html post.html index.html; do cmp -s ssg/templates/$f /check/orig_tpl_$f || guard_fail "ssg/templates/$f was modified"; done
for f in test_frontmatter.py test_markdown.py test_build.py; do cmp -s tests/$f /check/orig_$f || guard_fail "tests/$f was modified"; done
items 10 15 python3 /check/utrun.py --suite test_frontmatter=4 test_markdown=2 test_build=3
items 81 12 python3 /check/check_tags.py
finish
