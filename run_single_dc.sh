#!/usr/bin/env bash
# run_single_dc.sh
# Runs the single_deepcopy.py micro, produces perf stat + perf record and optional FlameGraph.

set -euo pipefail

# Paths
PYPERF_DIR="${PYPERF_DIR:-pyperformance-main}"
BM_SINGLE_REL="${BM_SINGLE:-$PYPERF_DIR/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py}"

# FlameGraph tools
FLAMEGRAPH_DIR="${FLAMEGRAPH_DIR:-$HOME/FlameGraph}"
STACKCOLLAPSE_PL="${STACKCOLLAPSE_PL:-$FLAMEGRAPH_DIR/stackcollapse-perf.pl}"
FLAMEGRAPH_PL="${FLAMEGRAPH_PL:-$FLAMEGRAPH_DIR/flamegraph.pl}"

# Defaults (fast & light)
PERF_FREQ_SINGLE="${PERF_FREQ_SINGLE:-99}"
CALLGRAPH_RECORD="${CALLGRAPH_RECORD:-fp}"     # 'fp' by default for speed

# Optional knobs
PIN_CPU="${PIN_CPU:-}"                         # e.g. PIN_CPU=0
PERF_RECORD_OPTS_EXTRA="${PERF_RECORD_OPTS_EXTRA:-}"  # e.g. "-e cycles:u"
SKIP_FLAMEGRAPH="${SKIP_FLAMEGRAPH:-0}"
TIMEOUT_SECS="${TIMEOUT_SECS:-180}"
SUDO="${SUDO:-}"

# Output dir (argument or default)
OUT_DIR="${1:-out_single_dc}"
mkdir -p "$OUT_DIR"

abspath() {
  python3 - "$1" <<'PY'
import os, sys
print(os.path.abspath(sys.argv[1]))
PY
}

BM_SINGLE="$(abspath "$BM_SINGLE_REL")"
[[ -f "$BM_SINGLE" ]] || { echo "ERROR: $BM_SINGLE not found"; exit 1; }

# perf stat (single run; detailed)
echo "== [single_deepcopy] perf stat =="
{
  echo "CMD: python3 $BM_SINGLE"
  echo "DATE: $(date)"
  echo
} > "${OUT_DIR}/perf_stat.txt"

cmd="python3 \"$BM_SINGLE\""
[[ -n "${PIN_CPU}" ]] && cmd="taskset -c ${PIN_CPU} ${cmd}"

set +e
perf stat -d -d -d -- bash -lc "$cmd" \
  1> >(tee "${OUT_DIR}/benchmark_stdout.txt") \
  2> >(tee "${OUT_DIR}/benchmark_stderr.txt" >&2)
echo $? > "${OUT_DIR}/exit_code.txt"
set -e

# perf record + (optional) flamegraph
echo "== [single_deepcopy] perf record (freq=${PERF_FREQ_SINGLE}, callgraph=${CALLGRAPH_RECORD}) =="
pushd "$OUT_DIR" >/dev/null
pycmd="python3 \"${BM_SINGLE}\""
[[ -n "${PIN_CPU}" ]] && pycmd="taskset -c ${PIN_CPU} ${pycmd}"

${SUDO} perf record -F "${PERF_FREQ_SINGLE}" --call-graph "${CALLGRAPH_RECORD}" ${PERF_RECORD_OPTS_EXTRA} -- bash -lc "${pycmd}"

if [[ "${SKIP_FLAMEGRAPH}" -eq 1 ]]; then
  echo "   -> SKIP_FLAMEGRAPH=1: leaving only perf.data"
  popd >/dev/null; exit 0
fi

if timeout "${TIMEOUT_SECS}" ${SUDO} perf script > out.perf ; then
  "${STACKCOLLAPSE_PL}" out.perf > out.folded
  "${FLAMEGRAPH_PL}" out.folded > flamegraph.svg
  gzip -f -9 out.folded || true
else
  echo "   !! perf script timed out, keeping perf.data"
fi

popd >/dev/null
echo "Done. Outputs in ${OUT_DIR}"
