#!/bin/bash
# graded score (tasks_qg): every stage runs and is counted, the script's ITEMS k/n are added, and the verdict is the
# same as with set -e (exit 1 if any stage failed); the last line is SCORE k/n
cd /work
export PYTHONDONTWRITEBYTECODE=1
fail=0; sk=0; sn=0
pass_() { sn=$((sn+1)); sk=$((sk+1)); }
miss() { sn=$((sn+1)); fail=1; }
cmp -s data/releases.txt /check/orig_releases.txt && pass_ || { echo "data/releases.txt was modified"; miss; }
cmp -s tests/test_vsort.py /check/orig_test_vsort.py && pass_ || { echo "tests/test_vsort.py was modified"; miss; }
# 2>&1: eval.py keeps the last 1500 characters of stdout+stderr; unittest writes to stderr and pushed SCORE out
python3 -m unittest discover -s tests -q 2>&1 && pass_ || miss
# the whole check runs under `timeout 60`; the script gets what is left, so a hang still ends with a SCORE line
left=$((55 - SECONDS)); [ $left -lt 1 ] && left=1   # timeout 0 would mean no limit
out=$(timeout $left python3 /check/check_semver.py 2>&1); rc=$?
printf '%s\n' "$out"
# sections weigh the same: the stages above (cmp, test -f, unittest) are one section, and each "SECTION name k/n" of the
# script is one more; SCORE = round(1000 * mean of the section pass ratios) / 1000 (a script that printed no section
# counts as one failed section)
score=$(printf '%s\n' "$out" | awk -v sk=$sk -v sn=$sn '
  /^SECTION [^ ]+ [0-9]+\/[0-9]+$/ { split($3, a, "/"); if (a[2] > 0) { s += a[1] / a[2]; c++ } }
  END { if (c == 0) { c = 1; s = 0 }; if (sn > 0) { s += sk / sn; c++ }; printf "%d", int(1000 * s / c + 0.5) }')
[ $rc -ne 0 ] && fail=1
echo "SCORE $score/1000"
exit $fail
