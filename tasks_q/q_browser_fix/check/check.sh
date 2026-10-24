#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in server.py static/login.html static/apply.html static/form.html; do
  cmp -s app/$f /check/app/$f || { echo "app/$f was modified"; exit 1; }
done
cmp -s data/applications.csv /check/orig_applications.csv || { echo "data/applications.csv was modified"; exit 1; }
python3 /check/run_check.py
