set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in vendor_a.csv vendor_b.csv vendor_c.csv; do cmp -s data/$f /check/orig_$f || { echo "data/$f was modified"; exit 1; }; done
for f in test_sniff.py test_normalize.py test_store.py; do cmp -s tests/$f /check/orig_$f || { echo "tests/$f was modified"; exit 1; }; done
python3 -m unittest discover -s tests -q
python3 /check/check_import.py
