#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in base.html post.html index.html; do cmp -s ssg/templates/$f /check/orig_tpl_$f || { echo "ssg/templates/$f was modified"; exit 1; }; done
for f in test_frontmatter.py test_markdown.py test_build.py; do cmp -s tests/$f /check/orig_$f || { echo "tests/$f was modified"; exit 1; }; done
python3 -m unittest discover -s tests -q
python3 /check/check_tags.py
