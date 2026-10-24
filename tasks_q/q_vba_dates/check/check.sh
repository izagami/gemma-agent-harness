#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s vba/Module1.bas /check/orig_Module1.bas || { echo "vba/Module1.bas was modified"; exit 1; }
cmp -s data/seikyu.csv /check/orig_seikyu.csv || { echo "data/seikyu.csv was modified"; exit 1; }
cmp -s out/expected_pay_schedule.txt /check/orig_expected_pay_schedule.txt || { echo "out/expected_pay_schedule.txt was modified"; exit 1; }
test -f pay_schedule.py || { echo "pay_schedule.py is missing"; exit 1; }
python3 /check/check_dates.py
