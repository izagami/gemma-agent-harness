set -e
cd /work
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || { echo "tests/test_cli.py was modified"; exit 1; }
cmp -s data/inventory.csv /check/inventory.csv || { echo "data/inventory.csv was modified"; exit 1; }
cmp -s data/inventory.csv.history /check/inventory.csv.history || { echo "data/inventory.csv.history was modified"; exit 1; }
test ! -e invtool/commands.py || { echo "invtool/commands.py still exists"; exit 1; }
test -f invtool/registry.py
for c in add adjust export help history list low move remove search show value; do
  test -f invtool/commands/$c.py || { echo "invtool/commands/$c.py missing"; exit 1; }
done
python3 -m unittest discover -s tests -q
python3 /check/check_registry.py /work
