#!/bin/bash
set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s docs/RULES.md /check/orig_RULES.md || { echo "docs/RULES.md was modified"; exit 1; }
cmp -s docs/POLICY.md /check/orig_POLICY.md || { echo "docs/POLICY.md was modified"; exit 1; }
python3 /check/check_fw.py
