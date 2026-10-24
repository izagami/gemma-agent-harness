set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || { echo "tests/test_cli.py was modified"; exit 1; }
for f in rates.json sample.csv; do cmp -s data/$f /check/$f || { echo "data/$f was modified"; exit 1; }; done
test -f tests/test_report.py || { echo "tests/test_report.py missing"; exit 1; }
python3 -m unittest discover -s tests -q
n=$(python3 -c "import unittest; print(unittest.defaultTestLoader.discover('tests', pattern='test_report.py').countTestCases())")
test "$n" -ge 3 || { echo "only $n tests in tests/test_report.py"; exit 1; }
python3 /check/check_report.py
