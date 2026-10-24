set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s data/holidays.txt /check/orig_holidays.txt || { echo "data/holidays.txt was modified"; exit 1; }
cmp -s tests/test_ops.py /check/orig_test_ops.py || { echo "tests/test_ops.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_bizdays.py
