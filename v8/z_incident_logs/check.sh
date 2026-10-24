set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
for f in tests/test_retry.py config/orders.ini config/gateway.ini docs/services.md; do cmp -s $f /check/$(basename $f) || { echo "$f was modified"; exit 1; }; done
sha256sum -c --quiet /check/logs.sha256 || { echo "logs/ were modified"; exit 1; }
python3 -c "from client.config import DEFAULTS; assert DEFAULTS == {'max_attempts': 6, 'base_delay_ms': 100, 'multiplier': 2.0, 'max_delay_ms': 5000, 'retry_on': (502, 503, 504)}, DEFAULTS" || { echo "DEFAULTS changed"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/test_hidden_retry.py -q
python3 /check/check_incident.py
