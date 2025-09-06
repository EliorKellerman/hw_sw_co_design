#pyperformance run -b deepcopy # Runs using the pyperformance library.
#python3 pyperformance-main/dev.py run -b deepcopy # Runs from the local copy of the pyperformance library.

# this file will summarise all the benchmark runs and measurments taken in the project
# it may include calls to other .sh files to run specific benchmark comparisons

echo "[*] Installing system prerequisites..."

if [ ! -d "$HOME/FlameGraph" ]; then
  echo "[*] Cloning FlameGraph tools..."
  git clone https://github.com/brendangregg/FlameGraph.git "$HOME/FlameGraph"
fi

echo "[*] Installing Python prerequisites..."
python3 -m pip install --upgrade pip setuptools wheel

# PyPerformance + PyPerf
python3 -m pip install pyperformance pyperf psutil packaging tomli

# PySpy for flamegraphs
python3 -m pip install py-spy

# AES library used by the crypto_pyaes benchmark
python3 -m pip install pyaes

# Make sure local copy.py / copy_opt.py is on PYTHONPATH if needed
export PYTHONPATH=$PYTHONPATH:$(pwd)

# DC
mkdir -p res/dc
# run DC benchmark with perf stat (baseline + optimised)
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark.py > res/dc/perf_stat_dc_baseline.txt 2>&1

perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark_opt.py > res/dc/perf_stat_dc_opt.txt 2>&1

python3 parse_perf_stat_compare.py \
  res/dc/perf_stat_dc_baseline.txt \
  res/dc/perf_stat_dc_opt.txt \
  -o res/dc/perf_stat_dc_compare.csv

# run single DC benchmark with flame graph using pyspy (baseline + optimised)
py-spy record --rate 25000 --subprocesses --output res/dc/flamegraph_dc_baseline.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py

py-spy record --rate 25000 --subprocesses --output res/dc/flamegraph_dc_opt.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py

# run DC benchmark with perf report (baseline + optimised)
perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > res/dc/perf_report_dc_baseline.txt

perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > res/dc/perf_report_dc_opt.txt

# run 2 versions of the full DC benchmark for performance comparison
python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark.py > res/dc/pyperformance_dc_baseline.txt

python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark_opt.py > res/dc/pyperformance_dc_opt.txt

# Parse & compare into CSV
python3 parse_pyperf_results.py \
  res/dc/pyperformance_dc_baseline.txt \
  res/dc/pyperformance_dc_opt.txt \
  -o res/dc/pyperformance_dc_compare.csv

# run all versions of the DC benchmark for detailed performance comparison
# python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark_versions_cmp.py > res/dc/pyperformance_dc_all_versions.txt