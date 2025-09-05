#pyperformance run -b deepcopy # Runs using the pyperformance library.
#python3 pyperformance-main/dev.py run -b deepcopy # Runs from the local copy of the pyperformance library.

# this file will summarise all the benchmark runs and measurments taken in the project
# it may include calls to other .sh files to run specific benchmark comparisons

# AES
mkdir -p res/aes
# run single AES benchmark with perf stat (baseline + optimised)
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py > res/aes/perf_stat_aes_baseline.txt 2>&1
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py > res/aes/perf_stat_aes_opt.txt 2>&1

python3 parse_perf_stat_compare.py \
  res/aes/perf_stat_aes_baseline.txt \
  res/aes/perf_stat_aes_opt.txt \
  -o res/aes/perf_stat_aes_compare.csv

# run single AES benchmark with flame graph using pyspy (baseline + optimised)
py-spy record --rate 25000 --subprocesses --output res/aes/flamegraph_aes_baseline.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py

py-spy record --rate 25000 --subprocesses --output res/aes/flamegraph_aes_opt.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py

# run AES benchmark with perf report (baseline + optimised)
perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > res/aes/perf_report_aes_baseline.txt

perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > res/aes/perf_report_aes_opt.txt

# run 2 versions of the full AES benchmark for performance comparison
python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/run_benchmark.py > res/aes/pyperformance_aes_baseline.txt

python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/run_benchmark_opt.py > res/aes/pyperformance_aes_opt.txt

# Parse & compare into CSV
python3 parse_pyperf_results.py \
  res/aes/pyperformance_aes_baseline.txt \
  res/aes/pyperformance_aes_opt.txt \
  -o res/aes/pyperformance_aes_compare.csv

# DC
mkdir -p res/dc
# run single DC benchmark with perf stat (baseline + optimised)
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py > res/dc/perf_stat_dc_baseline.txt 2>&1

perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py > res/dc/perf_stat_dc_opt.txt 2>&1

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