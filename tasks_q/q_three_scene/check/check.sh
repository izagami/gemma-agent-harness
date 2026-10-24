#!/bin/bash
set -e
cd /work
cmp -s lib/three.module.js /check/orig_three.module.js || { echo "lib/three.module.js was modified"; exit 1; }
cmp -s docs/SPEC.md /check/orig_SPEC.md || { echo "docs/SPEC.md was modified"; exit 1; }
test -f index.html || { echo "index.html missing"; exit 1; }
python3 /check/check_scene.py
