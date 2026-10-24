#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in server.py static/login.html static/requests.html data/requests.json; do
  cmp -s app/$f /check/app/$f || { echo "app/$f was modified"; exit 1; }
done
cmp -s data/approve_list.csv /check/orig_approve_list.csv || { echo "data/approve_list.csv was modified"; exit 1; }
test -f automation/approve.py || { echo "automation/approve.py does not exist"; exit 1; }
python3 /check/run_check.py
