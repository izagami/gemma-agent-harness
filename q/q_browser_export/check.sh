#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in server.py static/login.html static/orders.html data/orders.json; do
  cmp -s app/$f /check/app/$f || { echo "app/$f was modified"; exit 1; }
done
test -f automation/export.py || { echo "automation/export.py does not exist"; exit 1; }
grep -q playwright automation/export.py || { echo "automation/export.py does not use Playwright"; exit 1; }
python3 /check/run_check.py
