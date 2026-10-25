#!/bin/bash
# graded copy of tasks_v8/z_cmd_registry (tasks_v8g): same verdict, every stage counted, last line SCORE k/n
cd /work
source /check/grade_lib.sh
export PYTHONDONTWRITEBYTECODE=1
cmp -s tests/test_cli.py /check/test_cli.py || guard_fail "tests/test_cli.py was modified"
cmp -s data/inventory.csv /check/inventory.csv || guard_fail "data/inventory.csv was modified"
cmp -s data/inventory.csv.history /check/inventory.csv.history || guard_fail "data/inventory.csv.history was modified"
test ! -e invtool/commands.py; chk $? "invtool/commands.py still exists"
test -f invtool/registry.py; chk $? "invtool/registry.py missing"
miss=0
for c in add adjust export help history list low move remove search show value; do
  test -f invtool/commands/$c.py || { echo "invtool/commands/$c.py missing"; miss=1; }
done
chk $miss
items 8 15 python3 /check/utrun.py --suite test_cli=7
items 86 12 python3 /check/check_registry.py /work
finish
