#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/posts.jsonl /check/orig_posts.jsonl || { echo "data/posts.jsonl was modified"; exit 1; }
cmp -s tests/test_paginate.py /check/orig_test_paginate.py || { echo "tests/test_paginate.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_pages.py
