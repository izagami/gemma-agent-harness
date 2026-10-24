set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_render.py /check/test_render.py || { echo "tests/test_render.py was modified"; exit 1; }
cmp -s tests/onboarding.html /check/onboarding.html || { echo "tests/onboarding.html was modified"; exit 1; }
cmp -s docs/SYNTAX.md /check/SYNTAX.md || { echo "docs/SYNTAX.md was modified"; exit 1; }
for n in onboarding release style; do cmp -s examples/$n.txt /check/examples/$n.txt || { echo "examples/$n.txt was modified"; exit 1; }; done
python3 -m unittest discover -s tests -q
python3 /check/check_render.py
