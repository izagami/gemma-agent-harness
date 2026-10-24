#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s vba/Module1.bas /check/orig_Module1.bas || { echo "vba/Module1.bas was modified"; exit 1; }
cmp -s data/kokyaku.csv /check/orig_kokyaku.csv || { echo "data/kokyaku.csv was modified"; exit 1; }
cmp -s out/expected_customers_load.txt /check/orig_expected_customers_load.txt || { echo "out/expected_customers_load.txt was modified"; exit 1; }
test -f customer_clean.py || { echo "customer_clean.py is missing"; exit 1; }
python3 /check/check_text.py
