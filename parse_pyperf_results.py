#!/usr/bin/env python3
"""
Parse two pyperformance result files (baseline & optimized) and emit a comparison CSV.

Supports lines like:
.....................
deepcopy: Mean +- std dev: 665 us +- 4 us
.....................
crypto_pyaes: Mean +- std dev: 174 ms +- 1 ms

Output units are normalized with --unit {us,ms,s} (default: us).
"""

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Tuple

LINE_RE = re.compile(
    r'^(?P<name>[A-Za-z0-9_\-\.]+):\s*Mean\s*\+\-\s*std dev:\s*'
    r'(?P<mean>[\d\.]+)\s*(?P<unit>[munskµ]*s)\s*\+\-\s*(?P<std>[\d\.]+)\s*(?P<std_unit>[munskµ]*s)\s*$',
    re.IGNORECASE
)

_TO_US = {
    "us": 1.0,
    "µs": 1.0,  # in case of micro symbol
    "ms": 1000.0,
    "s":  1_000_000.0,
}

def to_us(value: float, unit: str) -> float:
    u = unit.strip().lower().replace("μ", "µ")  # normalize micro symbol
    if u not in _TO_US:
        # Fallback: assume microseconds
        return value
    return value * _TO_US[u]

def from_us(value_us: float, target_unit: str) -> float:
    t = target_unit.strip().lower().replace("μ", "µ")
    if t == "us" or t == "µs":
        return value_us
    if t == "ms":
        return value_us / 1000.0
    if t == "s":
        return value_us / 1_000_000.0
    # default: keep in us
    return value_us

def parse_file(path: Path) -> Dict[str, Tuple[float, float]]:
    results: Dict[str, Tuple[float, float]] = {}
    for line in path.read_text(errors="ignore").splitlines():
        m = LINE_RE.match(line.strip())
        if not m:
            continue
        name = m.group("name")
        mean = float(m.group("mean"))
        std  = float(m.group("std"))
        unit = m.group("unit")
        std_unit = m.group("std_unit")
        mean_us = to_us(mean, unit)
        std_us  = to_us(std, std_unit)
        results[name] = (mean_us, std_us)
    return results

def main():
    ap = argparse.ArgumentParser(description="Compare pyperformance results (baseline vs optimized).")
    ap.add_argument("baseline_file", type=Path)
    ap.add_argument("optimized_file", type=Path)
    ap.add_argument("-o", "--output", type=Path, default=Path("pyperf_compare.csv"))
    ap.add_argument("--unit", choices=["us", "ms", "s"], default="us",
                    help="Output unit (default: us).")
    args = ap.parse_args()

    base = parse_file(args.baseline_file)
    opt  = parse_file(args.optimized_file)

    # union of all benchmarks found
    names = sorted(set(base.keys()) | set(opt.keys()))

    with args.output.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([
            "Benchmark",
            f"Baseline Mean ({args.unit})", f"Baseline Std ({args.unit})",
            f"Optimized Mean ({args.unit})", f"Optimized Std ({args.unit})",
            f"Delta ({args.unit}) (Opt - Base)",
            "Improvement (%)"
        ])
        for name in names:
            b_mean_us, b_std_us = base.get(name, (float("nan"), float("nan")))
            o_mean_us, o_std_us = opt.get(name,  (float("nan"), float("nan")))

            b_mean = from_us(b_mean_us, args.unit) if b_mean_us == b_mean_us else float("nan")
            b_std  = from_us(b_std_us,  args.unit) if b_std_us  == b_std_us  else float("nan")
            o_mean = from_us(o_mean_us, args.unit) if o_mean_us == o_mean_us else float("nan")
            o_std  = from_us(o_std_us,  args.unit) if o_std_us  == o_std_us  else float("nan")

            if b_mean == b_mean and o_mean == o_mean and b_mean != 0.0:
                delta = o_mean - b_mean
                improvement = (b_mean - o_mean) / b_mean * 100.0
            else:
                delta = float("nan")
                improvement = float("nan")

            w.writerow([
                name,
                f"{b_mean:.6f}", f"{b_std:.6f}",
                f"{o_mean:.6f}", f"{o_std:.6f}",
                f"{delta:.6f}", f"{improvement:.2f}"
            ])

    print(f"Wrote {args.output}")

if __name__ == "__main__":
    main()
