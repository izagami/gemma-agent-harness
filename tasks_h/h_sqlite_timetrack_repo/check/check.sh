#!/bin/bash
# graded score: every stage runs and is counted; each "SECTION name k/n" of the script is one section, the protect +
# unittest stages are one more; SCORE = mean of the section ratios (x1000); exit 1 if anything failed
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
fail=0; sk=0; sn=0
pass_() { sn=$((sn+1)); sk=$((sk+1)); }
miss() { sn=$((sn+1)); fail=1; }
cmp -s docs/REPO.md /check/orig_REPO.md && pass_ || { echo "docs/REPO.md was modified"; miss; }
cmp -s data/make_db.py /check/orig_make_db.py && pass_ || { echo "data/make_db.py was modified"; miss; }
cmp -s data/schema.sql /check/orig_schema.sql && pass_ || { echo "data/schema.sql was modified"; miss; }
cmp -s tests/test_repo.py /check/orig_test_repo.py && pass_ || { echo "tests/test_repo.py was modified"; miss; }
python3 -m unittest discover -s tests -q 2>&1 | tail -12 && [ ${PIPESTATUS[0]} -eq 0 ] && pass_ || miss
left=$((55 - SECONDS)); [ $left -lt 1 ] && left=1
rc=0; out=$(timeout $left python3 /check/check_repo.py 2>&1) || rc=$?
printf '%s\n' "$out" | tail -c 1100
score=$(printf '%s\n' "$out" | awk -v sk=$sk -v sn=$sn '
  /^SECTION [^ ]+ [0-9]+\/[0-9]+$/ { split($3, a, "/"); if (a[2] > 0) { s += a[1] / a[2]; c++ } }
  END { if (c == 0) { c = 1; s = 0 }; if (sn > 0) { s += sk / sn; c++ }; printf "%d", int(1000 * s / c + 0.5) }')
[ $rc -ne 0 ] && fail=1
echo "SCORE $score/1000"
exit $fail
