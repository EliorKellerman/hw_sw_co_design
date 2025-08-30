#!/usr/bin/env bash
# run_benches.sh
# - Runs full deepcopy benchmark for multiple versions (baseline, merged, etc.)
# - Collects perf stat + perf record
# - Auto-chooses flamegraph generator:
#     * prefer:  perf script report flamegraph   (newer perf)
#     * else :   stackcollapse-perf.pl + flamegraph.pl (classic)
# - Writes perf stat summaries, including a wide CSV with a "% MERGED vs BASELINE" column

set -euo pipefail

############################################
# CONFIG
############################################

PYPERF_DIR="${PYPERF_DIR:-pyperformance-main}"

# ---- Warm mode (reuse venv so perf records only the benchmark) ----
WARM="${WARM:-1}"                               # 1 = use shared venv; 0 = unmanaged (pyperformance makes venvs)
VENV_DIR="${VENV_DIR:-.bench-venv-deepcopy}"    # shared venv location
CLEAN_VENV="${CLEAN_VENV:-0}"                   # 1 = force recreate
# -------------------------------------------------------------------

# Version commands (can be overridden via env)
if [[ "$WARM" == "1" ]]; then
  BASELINE_CMD="${BASELINE_CMD:-$VENV_DIR/bin/pyperformance run -b deepcopy}"
  MERGED_CMD="${MERGED_CMD:-$VENV_DIR/bin/python $PYPERF_DIR/dev.py run -b deepcopy}"
else
  BASELINE_CMD="${BASELINE_CMD:-pyperformance run -b deepcopy}"
  MERGED_CMD="${MERGED_CMD:-python3 $PYPERF_DIR/dev.py run -b deepcopy}"
fi

# FlameGraph tools (used only if builtin perf flamegraph is unavailable)
FLAMEGRAPH_DIR="${FLAMEGRAPH_DIR:-$HOME/FlameGraph}"
STACKCOLLAPSE_PL="${STACKCOLLAPSE_PL:-$FLAMEGRAPH_DIR/stackcollapse-perf.pl}"
FLAMEGRAPH_PL="${FLAMEGRAPH_PL:-$FLAMEGRAPH_DIR/flamegraph.pl}"

# perf sampling defaults
PERF_FREQ_FULL="${PERF_FREQ_FULL:-999}"         # default ~1000 Hz
CALLGRAPH_RECORD="${CALLGRAPH_RECORD:-fp}"     # 'fp' (fast) or 'dwarf' (detailed, slower)

# Optional knobs
PIN_CPU="${PIN_CPU:-}"                         # e.g. PIN_CPU=0
PERF_RECORD_OPTS_EXTRA="${PERF_RECORD_OPTS_EXTRA:-}"  # e.g. "-e cycles:u"

# perf stat opts: rely on perf default (single run), just add details
PERF_STAT_OPTS=( -d -d -d )

# timeouts for post-processing
TIMEOUT_SECS="${TIMEOUT_SECS:-180}"

# Output root
STAMP="$(date +%Y%m%d_%H%M%S)"
OUT_ROOT="${OUT_ROOT:-out_benches/${STAMP}}"

# sudo if needed
SUDO="${SUDO:-}"

# Remember the top directory so we can cd back for perf record commands
TOP_CWD="$(pwd)"

############################################
# Helpers
############################################

ensure_tools() {
  command -v perf >/dev/null 2>&1 || { echo "ERROR: perf not found"; exit 1; }
  command -v python3 >/dev/null 2>&1 || { echo "ERROR: python3 not found"; exit 1; }

  # If we won't build flamegraphs (SKIP_FLAMEGRAPH=1), we don't need either path.
  if [[ "${SKIP_FLAMEGRAPH:-0}" -ne 1 ]]; then
    if ! perf_has_builtin_flamegraph; then
      [[ -x "$STACKCOLLAPSE_PL" ]] || { echo "ERROR: $STACKCOLLAPSE_PL not found/executable"; exit 1; }
      [[ -x "$FLAMEGRAPH_PL"    ]] || { echo "ERROR: $FLAMEGRAPH_PL not found/executable"; exit 1; }
    fi
  fi
}

perf_has_builtin_flamegraph() {
  # Returns 0 if the installed perf supports: perf script report flamegraph
  perf script report flamegraph -h >/dev/null 2>&1
}

ensure_warm_venv() {
  [[ "$WARM" != "1" ]] && return 0
  if [[ "$CLEAN_VENV" == "1" && -d "$VENV_DIR" ]]; then
    echo "[warm] Recreating venv at $VENV_DIR..."
    pyperformance venv recreate --venv "$VENV_DIR" -b deepcopy
  elif [[ ! -d "$VENV_DIR" ]]; then
    echo "[warm] Creating venv at $VENV_DIR..."
    pyperformance venv create   --venv "$VENV_DIR" -b deepcopy
  else
    echo "[warm] Reusing venv at $VENV_DIR"
  fi
}

run_perf_stat() {
  local label="$1" outdir="$2" cmd="$3"
  echo "== [${label}] perf stat =="
  mkdir -p "$outdir"

  # Optional pinning
  if [[ -n "${PIN_CPU}" ]]; then
    cmd="taskset -c ${PIN_CPU} ${cmd}"
  fi

  {
    echo "CMD: $cmd"
    echo "DATE: $(date)"
    echo "PERF_STAT_OPTS: ${PERF_STAT_OPTS[*]}"
    [[ -n "${PIN_CPU}" ]] && echo "PINNED_CPU: ${PIN_CPU}"
    echo
  } > "${outdir}/perf_stat.txt"

  set +e
  ${SUDO} perf stat "${PERF_STAT_OPTS[@]}" -- bash -lc "$cmd" \
    1> >(tee "${outdir}/benchmark_stdout.txt") \
    2> >(tee "${outdir}/benchmark_stderr.txt" >&2)
  echo $? > "${outdir}/exit_code.txt"
  set -e
}

record_and_flamegraph_full() {
  local label="$1" outdir="$2" run_cmd="$3" freq="$4"
  echo "== [${label}] perf record on '${run_cmd}' (freq=${freq}, callgraph=${CALLGRAPH_RECORD}) =="
  mkdir -p "$outdir"
  pushd "$outdir" >/dev/null

  # Optional pinning
  if [[ -n "${PIN_CPU}" ]]; then
    run_cmd="taskset -c ${PIN_CPU} ${run_cmd}"
  fi

  # Run the recorded command from the original cwd so relative paths resolve,
  # but keep perf.data in $outdir (perf runs from here).
  ${SUDO} perf record -F "${freq}" --call-graph "${CALLGRAPH_RECORD}" ${PERF_RECORD_OPTS_EXTRA} \
    -- bash -lc "cd \"${TOP_CWD}\" && ${run_cmd}"

  if [[ "${SKIP_FLAMEGRAPH:-0}" -eq 1 ]]; then
    echo "   -> SKIP_FLAMEGRAPH=1: leaving only perf.data"
    popd >/dev/null; return
  fi

  # Auto choose flamegraph path
  if perf_has_builtin_flamegraph; then
    echo "-> Using builtin: perf script report flamegraph"
    set +e
    perf script report flamegraph --title "${label}" --minwidth 0.5 --output flamegraph.html 2>/dev/null
    rc=$?
    if [[ $rc -ne 0 ]]; then
      perf script report flamegraph > flamegraph.html 2>/dev/null
      rc=$?
    fi
    set -e
    if [[ $rc -ne 0 || ! -s flamegraph.html ]]; then
      echo "   !! builtin flamegraph failed; falling back to Perl tools"
      ${SUDO} perf script > out.perf
      "${STACKCOLLAPSE_PL}" out.perf > out.folded
      "${FLAMEGRAPH_PL}"    out.folded > flamegraph.svg
      gzip -f -9 out.folded || true
    fi
  else
    echo "-> Using classic FlameGraph scripts"
    ${SUDO} perf script > out.perf
    "${STACKCOLLAPSE_PL}" out.perf > out.folded
    "${FLAMEGRAPH_PL}"    out.folded > flamegraph.svg
    gzip -f -9 out.folded || true
  fi

  popd >/dev/null
}

run_version() {
  local version="$1" run_cmd="$2"
  echo "=============================="
  echo " Running version: ${version}"
  echo "=============================="

  local vdir="${OUT_ROOT}/${version}"
  local full_dir="${vdir}/full_benchmark"
  mkdir -p "${full_dir}"

  run_perf_stat     "${version}/full_benchmark" "${full_dir}" "${run_cmd}"
  record_and_flamegraph_full "${version}/full_benchmark" "${full_dir}" "${run_cmd}" "${PERF_FREQ_FULL}"
}

############################################
# Versions
############################################
VERSIONS=(
  "BASELINE:::${BASELINE_CMD}"
  "MERGED:::${MERGED_CMD}"
)

############################################
# CSV Summary (adds % MERGED vs BASELINE)
############################################
summarize_perf_stats() {
  local long_csv="${OUT_ROOT}/perf_stat_long.csv"
  echo "Suite,Metric,Unit,Version,Value" > "$long_csv"

  for vdir in "${OUT_ROOT}"/*; do
    [[ -d "$vdir" ]] || continue
    version="$(basename "$vdir")"
    perf_stderr="${vdir}/full_benchmark/benchmark_stderr.txt"
    [[ -f "$perf_stderr" ]] || continue

    awk -v SUITE="full_benchmark" -v VER="$version" '
      /^[ \t]*[0-9]/ {
        line=$0; sub(/^[ \t]+/,"",line)
        match(line,/^([0-9][0-9,\.]*)[ \t]+/,m)
        if (!m[1]) next
        val=m[1]; gsub(",","",val)
        sub(/^[0-9][0-9,\.]*[ \t]+/,"",line)
        metric=line; sub(/[ \t]*#.*$/,"",metric)
        unit=""
        if (match(metric,/\(([a-zA-Z%\/]+)\)/,u)) { unit=u[1] }
        sub(/[ \t]*\(.*\).*$/,"",metric)
        print SUITE "," metric "," unit "," VER "," val
      }
    ' "$perf_stderr" >> "$long_csv"
  done

  # Pivot to wide, and add % MERGED vs BASELINE
  python3 - <<'PY' "$OUT_ROOT"
import os, sys, pandas as pd

root = sys.argv[1]
long_csv = os.path.join(root, "perf_stat_long.csv")
if not os.path.isfile(long_csv):
    print("No perf_stat_long.csv; skipping.")
    raise SystemExit(0)

df = pd.read_csv(long_csv)

# Build a metric label that keeps the unit
df['MetricLabel'] = df.apply(
    lambda r: f"{r['Metric']}" + (f" ({r['Unit']})" if isinstance(r['Unit'], str) and r['Unit'] not in ("", "nan") else ""),
    axis=1
)

sub = df[df['Suite']=="full_benchmark"].copy()
wide = sub.pivot_table(index='MetricLabel', columns='Version', values='Value', aggfunc='first').sort_index()

if "BASELINE" in wide.columns and "MERGED" in wide.columns:
    pct = (wide["BASELINE"] - wide["MERGED"]) / wide["BASELINE"] * 100.0
    wide.insert(len(wide.columns), "MERGED vs BASELINE (%)", pct.round(2))

out = os.path.join(root, "perf_stat_full_benchmark_wide.csv")
wide.to_csv(out)
print(f"Wrote {out}")
PY
}

############################################
# main
############################################
main() {
  ensure_tools
  echo "Output root: ${OUT_ROOT}"
  mkdir -p "${OUT_ROOT}"

  ensure_warm_venv

  for entry in "${VERSIONS[@]}"; do
    label="${entry%%:::*}"
    cmd="${entry#*:::}"
    run_version "${label}" "${cmd}"
  done

  summarize_perf_stats
  echo "All done. Results in ${OUT_ROOT}"
}

main "$@"
