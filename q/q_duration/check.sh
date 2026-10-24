set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_durfmt.py /check/orig_test_durfmt.py || { echo "tests/test_durfmt.py was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_durfmt.py
