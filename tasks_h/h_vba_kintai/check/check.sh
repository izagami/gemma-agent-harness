#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s vba/Module1.bas /check/orig_Module1.bas || { echo "vba/Module1.bas was modified"; exit 1; }
cmp -s data/kintai.csv /check/orig_kintai.csv || { echo "data/kintai.csv was modified"; exit 1; }
cmp -s out/expected_kyuyo_202604.txt /check/orig_expected_kyuyo_202604.txt || { echo "out/expected_kyuyo_202604.txt was modified"; exit 1; }
test -f kintai.py || { echo "kintai.py is missing"; exit 1; }
python3 /check/check_kintai.py
