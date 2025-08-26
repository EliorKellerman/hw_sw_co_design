pyperformance run -b deepcopy # Runs using the pyperformance library.
python3 pyperformance-main/dev.py run -b deepcopy # Runs from the local copy of the pyperformance library.


## run and generate flamegraph
perf record -F 9 --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark.py
perf script > out.perf
perf script | ~/FlameGraph/stackcollapse-perf.pl > out.folded
~/FlameGraph/flamegraph.pl out.folded > flamegraph.svg

## run and generate flamegraph - single deepcopy mem
perf record -F 99 --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py
perf script > out.perf
perf script | ~/FlameGraph/stackcollapse-perf.pl > out_single_dc.folded
~/FlameGraph/flamegraph.pl out_single_dc.folded > flamegraph.svg