set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || { echo "tests/test_cli.py was modified"; exit 1; }
test ! -e tool/legacy_settings.py || { echo "tool/legacy_settings.py still exists"; exit 1; }
if grep -rl --include='*.py' legacy_settings . ; then echo "files above still mention legacy_settings"; exit 1; fi
test -f tool/settings.py
python3 -m unittest discover -s tests -q
python3 /check/check_settings.py /work
