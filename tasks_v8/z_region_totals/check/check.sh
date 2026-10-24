#!/bin/bash
set -eo pipefail
cd /work
export PYTHONDONTWRITEBYTECODE=1
sha256sum -c --quiet /check/protected.sha256 || { echo "config/, data/, tests/ or docs/ were modified"; exit 1; }
python3 -m unittest discover -s tests -q
test -f out/2026-09.txt || { echo "out/2026-09.txt missing"; exit 1; }
cmp -s out/2026-09.txt /check/exp/seed-2026-09.txt || { echo "out/2026-09.txt is wrong"; exit 1; }
test -f cause.txt || { echo "cause.txt missing"; exit 1; }
c=$(tr 'A-Z' 'a-z' < cause.txt)
grep -q "k07" <<<"$c" || { echo "cause.txt does not name the store id"; exit 1; }
grep -q "refunds/posmate/2026-09.csv" <<<"$c" || { echo "cause.txt does not name the refunds file"; exit 1; }
mkdir -p /tmp/elsewhere && cd /tmp/elsewhere
python3 /work/report.py --month 2026-09 | cmp -s - /check/exp/seed-2026-09.txt || { echo "report 2026-09 wrong"; exit 1; }
python3 /work/report.py --month 2026-08 | cmp -s - /check/exp/seed-2026-08.txt || { echo "report 2026-08 wrong"; exit 1; }
for m in 09 10; do
  python3 /work/report.py --month 2026-$m --data /check/fresh/data --config /check/fresh/config | cmp -s - /check/exp/fresh-2026-$m.txt || { echo "report on other data (2026-$m) wrong"; exit 1; }
done
echo "region totals OK"
