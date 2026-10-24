#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/invoice_0412.csv /check/orig_invoice_0412.csv || { echo "data/invoice_0412.csv was modified"; exit 1; }
cmp -s tests/test_invoice.py /check/orig_test_invoice.py || { echo "tests/test_invoice.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_tax.py
