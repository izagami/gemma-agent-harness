set -e
cd /work
for f in test_dates.py test_invoice.py; do cmp -s tests/$f /check/$f || { echo "tests/$f was modified"; exit 1; }; done
cmp -s docs/FORMAT.md /check/FORMAT.md || { echo "docs/FORMAT.md was modified"; exit 1; }
for f in plans.csv subscriptions.csv; do cmp -s data/$f /check/$f || { echo "data/$f was modified"; exit 1; }; done
export PYTHONDONTWRITEBYTECODE=1
python3 -m unittest discover -s tests -q
python3 /check/check_billing.py
