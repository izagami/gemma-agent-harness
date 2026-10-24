#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s vba/Module1.bas /check/orig_Module1.bas || { echo "vba/Module1.bas was modified"; exit 1; }
cmp -s data/uriage_meisai.csv /check/orig_uriage_meisai.csv || { echo "data/uriage_meisai.csv was modified"; exit 1; }
cmp -s out/expected_report_202604.txt /check/orig_expected_report_202604.txt || { echo "out/expected_report_202604.txt was modified"; exit 1; }
test -f sales_report.py || { echo "sales_report.py is missing"; exit 1; }
python3 /check/check_sales.py
