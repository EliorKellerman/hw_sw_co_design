#!/usr/bin/env bash
# make_flame.sh
# Post-process a perf.data into a FlameGraph.
# Input: a directory that contains perf.data (e.g., out_benches/<run>/<version>/<suite>)
# Output: out.perf, out.folded(.gz), flamegraph.svg in the same directory.

# ############################### #USAGE ###############################
# # From your project root:
# chmod +x make_flame.sh

# # Post-process a specific suite dir that contains perf.data, e.g.:
# ./make_flame.sh out_benches/20250830_155441/BASELINE/full_benchmark
# ./make_flame.sh out_benches/20250830_155441/MERGED/single_deepcopy

# # Optional env overrides:
# TIMEOUT_SECS=600 FLAMEGRAPH_DIR=~/FlameGraph ./make_flame.sh <suite-dir>



set -euo pipefail

DIR="${1:-}"
if [[ -z "$DIR" ]]; then
  echo "Usage: $0 path/to/.../<VERSION>/<suite>   # directory containing perf.data"
  exit 1
fi

# Config (overridable via env)
TIMEOUT_SECS="${TIMEOUT_SECS:-120}" 
FLAMEGRAPH_DIR="${FLAMEGRAPH_DIR:-$HOME/FlameGraph}"
FLAMEGRAPH_PL="${FLAMEGRAPH_PL:-$FLAMEGRAPH_DIR/flamegraph.pl}"

# Checks
[[ -f "$DIR/perf.data" ]] || { echo "ERROR: $DIR/perf.data not found"; exit 2; }
[[ -x "$STACKCOLLAPSE_PL" ]] || { echo "ERROR: $STACKCOLLAPSE_PL not found/executable"; exit 3; }
[[ -x "$FLAMEGRAPH_PL" ]] || { echo "ERROR: $FLAMEGRAPH_PL not found/executable"; exit 4; }
command -v perf >/dev/null 2>&1 || { echo "ERROR: perf not found"; exit 5; }

pushd "$DIR" >/dev/null

echo "-> perf script (generating out.perf)..."
if ! timeout "${TIMEOUT_SECS}" perf script > out.perf ; then
  echo "!! perf script timed out after ${TIMEOUT_SECS}s"
  exit 6
fi
echo "   lines in out.perf: $(wc -l < out.perf)"

echo "-> stackcollapse-perf.pl (generating out.folded)..."
if ! timeout "${TIMEOUT_SECS}" "$STACKCOLLAPSE_PL" out.perf > out.folded ; then
  echo "!! stackcollapse timed out after ${TIMEOUT_SECS}s"
  exit 7
fi
echo "   lines in out.folded: $(wc -l < out.folded)"

echo "-> flamegraph.pl (generating flamegraph.svg)..."
if ! timeout "${TIMEOUT_SECS}" "$FLAMEGRAPH_PL" out.folded > flamegraph.svg ; then
  echo "!! flamegraph generation timed out after ${TIMEOUT_SECS}s"
  exit 8
fi
gzip -f -9 out.folded || true
echo "Done: $(pwd)/flamegraph.svg"

popd >/dev/null
