#!/bin/bash
# graded score (tasks_qg): every stage runs and is counted, the script's ITEMS k/n are added, and the verdict is the
# same as with set -e (exit 1 if any stage failed); the last line is SCORE k/n
cd /work
export PYTHONDONTWRITEBYTECODE=1
fail=0; sk=0; sn=0
pass_() { sn=$((sn+1)); sk=$((sk+1)); }
miss() { sn=$((sn+1)); fail=1; }
cmp -s data/invoice_0412.csv /check/orig_invoice_0412.csv && pass_ || { echo "data/invoice_0412.csv was modified"; miss; }
cmp -s tests/test_invoice.py /check/orig_test_invoice.py && pass_ || { echo "tests/test_invoice.py was modified"; miss; }
# 2>&1: eval.py keeps the last 1500 characters of stdout+stderr; unittest writes to stderr and pushed SCORE out
python3 -m unittest discover -s tests -q 2>&1 && pass_ || miss
# the whole check runs under `timeout 60`; the script gets what is left, so a hang still ends with a SCORE line
left=$((55 - SECONDS)); [ $left -lt 1 ] && left=1   # timeout 0 would mean no limit
out=$(timeout $left python3 /check/check_tax.py 2>&1); rc=$?
printf '%s\n' "$out"
it=$(printf '%s\n' "$out" | grep -E '^ITEMS [0-9]+/[0-9]+$' | tail -1)
if [ -n "$it" ]; then k=${it#ITEMS }; n=${k#*/}; k=${k%/*}; sk=$((sk+k)); sn=$((sn+n)); else sn=$((sn+1)); fi
[ $rc -ne 0 ] && fail=1
echo "SCORE $sk/$sn"
exit $fail
