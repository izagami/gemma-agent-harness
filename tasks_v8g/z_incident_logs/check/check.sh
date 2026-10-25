#!/bin/bash
# graded copy of tasks_v8/z_incident_logs (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
for f in tests/test_retry.py config/orders.ini config/gateway.ini docs/services.md; do cmp -s $f /check/$(basename $f) || guard_fail "$f was modified"; done
sha256sum -c --quiet /check/logs.sha256 || guard_fail "logs/ were modified"
timeout "$(left)" python3 -c "from client.config import DEFAULTS; assert DEFAULTS == {'max_attempts': 6, 'base_delay_ms': 100, 'multiplier': 2.0, 'max_delay_ms': 5000, 'retry_on': (502, 503, 504)}, DEFAULTS" || guard_fail "DEFAULTS changed"
items 4 15 python3 /check/utrun.py --suite test_retry=3
items 12 15 python3 /check/utrun.py --file /check/test_hidden_retry.py test_hidden_retry=12
items 5 8 python3 /check/check_incident.py
finish
