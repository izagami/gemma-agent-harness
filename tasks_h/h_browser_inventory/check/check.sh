#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in server.py static/login.html static/stock.html data/stock.json; do
  cmp -s app/$f /check/app/$f || { echo "app/$f was modified"; exit 1; }
done
test -f automation/inventory.py || { echo "automation/inventory.py does not exist"; exit 1; }
grep -q playwright automation/inventory.py || { echo "automation/inventory.py does not use Playwright"; exit 1; }
python3 /check/run_check.py
