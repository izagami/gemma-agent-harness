# Shared by the tasks_v8g checkers (a copy lives in every check/ dir; sourced by check.sh).
# Graded copy of tasks_v8: every stage runs (no set -e) and its individual checks are counted; the verdict is the
# same as tasks_v8 (exit 1 if any stage failed); the LAST line is `SCORE k/n`. A failed anti-tamper guard
# (a protected file was modified) keeps failing and gives SCORE 0/n.
# eval.py keeps the last 1500 chars of stdout+stderr (stderr appended AFTER stdout): send all stderr to stdout so
# that nothing (a traceback, a sha256sum warning) can land behind the SCORE line
exec 2>&1
K=0; N=0; fail=0; guard=0

# chk RC [message]: one counted item, passed when RC is 0
chk() { N=$((N+1)); if [ "$1" -eq 0 ]; then K=$((K+1)); else fail=1; [ -n "$2" ] && echo "$2"; fi; return 0; }

# guard_fail message: a protected file was modified -> verdict fail, score 0
guard_fail() { echo "$1"; guard=1; fail=1; }

# seconds left of the 60 s budget (`timeout 60 bash check.sh`), keeping 3 s for the SCORE line
left() { local l=$((57 - SECONDS)); [ $l -lt 1 ] && l=1; echo $l; }

# items NFIXED TAIL cmd...: run cmd, show the last TAIL lines of its output, add its `ITEMS k/n` (k of NFIXED; no
# ITEMS line, e.g. a crash or timeout, counts 0) and fail the verdict if it exited non-zero
items() {
  local nf=$1 tl=$2; shift 2
  local out rc m k
  out=$(timeout "$(left)" "$@" 2>&1); rc=$?
  printf '%s\n' "$out" | grep -vE '^ITEMS [0-9]+/[0-9]+$' | tail -n "$tl"
  m=$(printf '%s\n' "$out" | grep -E '^ITEMS [0-9]+/[0-9]+$' | tail -1)
  k=0; [ -n "$m" ] && { k=${m#ITEMS }; k=${k%/*}; }
  [ "$k" -gt "$nf" ] && k=$nf
  if [ $rc -ne 0 ]; then fail=1; [ "$k" -ge "$nf" ] && k=$((nf - 1)); [ $k -lt 0 ] && k=0; fi
  K=$((K + k)); N=$((N + nf))
  return 0
}

finish() {
  [ $guard -ne 0 ] && K=0
  echo "SCORE $K/$N"
  exit $fail
}
