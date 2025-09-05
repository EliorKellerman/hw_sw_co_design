#!/usr/bin/env python3
"""
Compare two `perf stat` outputs (baseline vs optimized) and emit a CSV.

Supported patterns (typical `perf stat -r 5 -d -d -d` output):
  200.74 msec task-clock                #    0.978 CPUs utilized           ( +-  0.16% )
          11      context-switches      #   54.594 /sec                    ( +- 16.76% )
   521,061,541      cycles              #    2.586 GHz                     ( +-  0.17% )  (29.67%)
          0.205303 +- 0.000699 seconds time elapsed  ( +-  0.34% )

Notes:
- Ignores "<not supported>" lines.
- Tries to capture a single "Unit" (e.g., "msec" for task-clock, "seconds" for time elapsed).
- Keeps units as-is (no normalization), since perf mixes units per metric.
- Adds Delta and % Improvement columns (positive % means Optimized is faster/smaller).
"""

from __future__ import annotations
import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Tuple, Optional

# Regex for normal counter lines (value [unit] metric ... # comment)
# Examples:
#   200.74 msec task-clock                #    0.978 CPUs utilized           ( +-  0.16% )
#   521,061,541      cycles               #    2.586 GHz                     ( +-  0.17% )
LINE_RE = re.compile(
    r""" ^
        \s*
        (?P<value>[0-9][0-9,\.]*)           # numeric value (commas allowed)
        \s+
        (?:(?P<unit>[A-Za-z/%\-]+)\s+)?     # optional unit token (e.g., msec)
        (?P<metric>[A-Za-z0-9_\-./]+)       # metric name (e.g., task-clock, cycles)
        (?: \s+ \# \s* (?P<comment>.*) )?   # optional comment after '#'
        \s* $
    """,
    re.VERBOSE,
)

# Regex for "time elapsed" summary with mean +- std:
#   0.205303 +- 0.000699 seconds time elapsed  ( +-  0.34% )
TIME_ELAPSED_RE = re.compile(
    r""" ^
        \s*
        (?P<mean>[0-9]+(?:\.[0-9]+)?)      # mean value
        \s* \+\- \s*
        (?P<std>[0-9]+(?:\.[0-9]+)?)       # stddev
        \s*
        (?P<unit>[A-Za-z/%\-]+)            # unit (e.g., seconds)
        \s+ time \s+ elapsed
        (?: \s* \( .* \) )?                # optional "( +- x% )"
        \s* $
    """,
    re.VERBOSE,
)

def _parse_number(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except Exception:
        return None

def parse_perf_file(path: Path) -> Dict[str, Tuple[float, str, Optional[float]]]:
    """
    Returns:
      dict: metric -> (value, unit, stddev_or_None)

    For "time elapsed", we store the MEAN as value and STDDEV as stddev.
    For all other counters, stddev is left as None (perf prints mean±std% differently there).
    """
    metrics: Dict[str, Tuple[float, str, Optional[float]]] = {}

    text = path.read_text(errors="ignore")
    for raw in text.splitlines():
        line = raw.strip()

        # Skip unsupported lines
        if "<not supported>" in line:
            continue

        # Try time elapsed special case
        mtime = TIME_ELAPSED_RE.match(line)
        if mtime:
            mean = _parse_number(mtime.group("mean"))
            std  = _parse_number(mtime.group("std"))
            unit = (mtime.group("unit") or "").strip()
            if mean is not None:
                metrics["time-elapsed"] = (mean, unit, std)
            continue

        # Try generic counter line
        m = LINE_RE.match(line)
        if not m:
            continue

        val = _parse_number(m.group("value"))
        if val is None:
            continue

        unit = (m.group("unit") or "").strip()
        metric = (m.group("metric") or "").strip()

        # Heuristic: if metric looks like a unit, and unit is empty, try to fix.
        # (Usually not needed, but kept for odd outputs.)
        metrics[metric] = (val, unit, None)

    return metrics

def compare(
    base: Dict[str, Tuple[float, str, Optional[float]]],
    opt: Dict[str, Tuple[float, str, Optional[float]]],
) -> Dict[str, Tuple[Optional[float], str, Optional[float], Optional[float], str, Optional[float], Optional[float]]]:
    """
    Returns:
      dict: metric -> (
        base_val, base_unit, base_std,
        opt_val,  opt_unit,  opt_std,
        delta, improvement_pct
      )
    """
    all_keys = sorted(set(base.keys()) | set(opt.keys()))
    out = {}
    for k in all_keys:
        b = base.get(k)
        o = opt.get(k)

        b_val = b[0] if b else None
        b_unit = b[1] if b else ""
        b_std = b[2] if b else None

        o_val = o[0] if o else None
        o_unit = o[1] if o else ""
        o_std = o[2] if o else None

        delta = None
        improvement = None
        if (b_val is not None) and (o_val is not None):
            delta = o_val - b_val
            if b_val != 0:
                # For "better is lower" metrics (time, task-clock, cycles, misses),
                # improvement% = (baseline - optimized) / baseline * 100
                improvement = (b_val - o_val) / b_val * 100.0

        out[k] = (b_val, b_unit, b_std, o_val, o_unit, o_std, delta, improvement)
    return out

def main():
    ap = argparse.ArgumentParser(description="Compare two perf stat outputs (baseline vs optimized) into a CSV.")
    ap.add_argument("baseline_file", type=Path, help="perf stat output file (baseline)")
    ap.add_argument("optimized_file", type=Path, help="perf stat output file (optimized)")
    ap.add_argument("-o", "--output", type=Path, default=Path("perf_stat_compare.csv"))
    args = ap.parse_args()

    base = parse_perf_file(args.baseline_file)
    opt  = parse_perf_file(args.optimized_file)

    comp = compare(base, opt)

    with args.output.open("w", newline="") as f:
        w = csv.writer(f)
        # Only the 4 essential columns
        w.writerow([
            "Metric",
            "Baseline Value",
            "Optimized Value",
            "Delta (Opt - Base)"
        ])
        for metric, (b_val, b_unit, b_std, o_val, o_unit, o_std, delta, improvement) in comp.items():
            def fmt(x, dig=6):
                if x is None:
                    return ""
                return f"{x:.{dig}f}"
            w.writerow([
                metric,
                fmt(b_val),
                fmt(o_val),
                fmt(delta),
            ])


    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
