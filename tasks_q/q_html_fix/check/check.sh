#!/bin/bash
set -e
cd /work
cmp -s data.js /check/orig_data.js || { echo "data.js was modified"; exit 1; }
cmp -s docs/README.md /check/orig_README.md || { echo "docs/README.md was modified"; exit 1; }
python3 /check/check_dash.py
