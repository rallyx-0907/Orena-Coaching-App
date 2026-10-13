#!/bin/sh
# Runs every Node contract gate listed in scripts/node_gates.txt, several at a time.
#
# The gates are independent processes (each builds its own state; the one that needs a scratch directory makes a
# unique one), so running them in parallel changes how long the batch takes, not what it checks. Every gate still
# runs, a failing gate prints its own output, and the script exits non-zero if any failed.
#
#   sh scripts/run_node_gates.sh            # all gates, 4 at a time
#   JOBS=8 sh scripts/run_node_gates.sh     # more parallelism
#   sh scripts/run_node_gates.sh scripts/test_orena_kit.mjs   # just these gates (local iteration)
set -u
cd "$(dirname "$0")/.." || exit 1
JOBS="${JOBS:-4}"

if [ "$#" -gt 0 ]; then
  printf '%s\n' "$@" > "${TMPDIR:-/tmp}/orena_node_gates.$$"
  list="${TMPDIR:-/tmp}/orena_node_gates.$$"
else
  list="scripts/node_gates.txt"
fi

xargs -P "$JOBS" -I '{}' sh -c '
  out=$(node "$1" 2>&1) || { echo "::error::$1 failed"; echo "$out"; exit 1; }
' _ '{}' < "$list"
status=$?
[ "$#" -gt 0 ] && rm -f "$list"
if [ "$status" -ne 0 ]; then
  echo "One or more Node gates failed."
  exit 1
fi
echo "All Node gates passed."
