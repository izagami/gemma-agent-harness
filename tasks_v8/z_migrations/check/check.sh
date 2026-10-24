#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || { echo "tests/test_cli.py was modified"; exit 1; }
cmp -s migrations/001_initial.sql /check/001_initial.sql || { echo "migrations/001_initial.sql was modified"; exit 1; }
cmp -s migrations/002_add_pinned.sql /check/002_add_pinned.sql || { echo "migrations/002_add_pinned.sql was modified"; exit 1; }
python3 -m unittest discover -s tests -q
python3 /check/check_mig.py /work
