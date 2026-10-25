#!/bin/bash
# graded copy of tasks_v8/z_region_totals (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
set -o pipefail
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
sha256sum -c --quiet /check/protected.sha256 || guard_fail "config/, data/, tests/ or docs/ were modified"
items 7 15 python3 /check/utrun.py --suite test_config=3 test_fmt=2 test_stores=1
test -f out/2026-09.txt; chk $? "out/2026-09.txt missing"
cmp -s out/2026-09.txt /check/exp/seed-2026-09.txt; chk $? "out/2026-09.txt is wrong"
test -f cause.txt; chk $? "cause.txt missing"
c=$(tr 'A-Z' 'a-z' 2>/dev/null < cause.txt)
grep -q "k07" <<<"$c"; chk $? "cause.txt does not name the store id"
grep -q "refunds/posmate/2026-09.csv" <<<"$c"; chk $? "cause.txt does not name the refunds file"
mkdir -p /tmp/elsewhere && cd /tmp/elsewhere
timeout "$(left)" python3 /work/report.py --month 2026-09 | cmp -s - /check/exp/seed-2026-09.txt; chk $? "report 2026-09 wrong"
timeout "$(left)" python3 /work/report.py --month 2026-08 | cmp -s - /check/exp/seed-2026-08.txt; chk $? "report 2026-08 wrong"
for m in 09 10; do
  timeout "$(left)" python3 /work/report.py --month 2026-$m --data /check/fresh/data --config /check/fresh/config | cmp -s - /check/exp/fresh-2026-$m.txt; chk $? "report on other data (2026-$m) wrong"
done
[ $fail -eq 0 ] && echo "region totals OK"
finish
