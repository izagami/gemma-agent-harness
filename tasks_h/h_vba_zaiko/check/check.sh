#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s vba/Module1.bas /check/orig_Module1.bas || { echo "vba/Module1.bas was modified"; exit 1; }
cmp -s data/nyushukko.csv /check/orig_nyushukko.csv || { echo "data/nyushukko.csv was modified"; exit 1; }
cmp -s data/hinmoku.csv /check/orig_hinmoku.csv || { echo "data/hinmoku.csv was modified"; exit 1; }
cmp -s out/expected_zaiko_20260430.txt /check/orig_expected_zaiko_20260430.txt || { echo "out/expected_zaiko_20260430.txt was modified"; exit 1; }
test -f zaiko_hyoka.py || { echo "zaiko_hyoka.py is missing"; exit 1; }
python3 /check/check_zaiko.py
