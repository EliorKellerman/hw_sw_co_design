#pyperformance run -b deepcopy # Runs using the pyperformance library.
#python3 pyperformance-main/dev.py run -b deepcopy # Runs from the local copy of the pyperformance library.

# this file will summarise all the benchmark runs and measurments taken in the project
# it may include calls to other .sh files to run specific benchmark comparisons

# AES
# run single AES benchmark with perf stat (baseline + optimised)
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py > perf_stat_aes_baseline.txt 2>&1

perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py > perf_stat_aes_opt.txt 2>&1

# run single AES benchmark with flame graph using pyspy (baseline + optimised)
py-spy record --rate 25000 --subprocesses --output flamegraph_aes_baseline.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py

py-spy record --rate 25000 --subprocesses --output flamegraph_aes_opt.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py

# run AES benchmark with perf report (baseline + optimised)
perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > perf_report_aes_baseline.txt

perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/single_aes_opt.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > perf_report_aes_opt.txt

# run 2 versions of the full AES benchmark for performance comparison
python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/run_benchmark.py

python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_crypto_pyaes/run_benchmark_opt.py

# DC
# run single DC benchmark with perf stat (baseline + optimised)
perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py > perf_stat_dc_baseline.txt 2>&1

perf stat -r 5 -d -d -d -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py > perf_stat_dc_opt.txt 2>&1

# run single DC benchmark with flame graph using pyspy (baseline + optimised)
py-spy record --rate 25000 --subprocesses --output flamegraph_dc_baseline.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py

py-spy record --rate 25000 --subprocesses --output flamegraph_dc_opt.svg --format flamegraph --nonblocking  -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py

# run DC benchmark with perf report (baseline + optimised)
perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > perf_report_dc_baseline.txt

perf record --call-graph dwarf -- python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/single_deepcopy_opt.py
perf report --stdio --call-graph graph,0,caller  --sort=symbol  --no-children --percentage relative > perf_report_dc_opt.txt

# run 2 versions of the full DC benchmark for performance comparison
python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark.py

python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark_opt.py

# run all versions of the DC benchmark for detailed performance comparison
python3 pyperformance-main/pyperformance/data-files/benchmarks/bm_deepcopy/run_benchmark_versions_cmp.py

# TODO: add a script that automatically compares the perf stat results and summarises them in a table (bot AES and DC) in an out file
# TODO: add a script that automatically compares the pyperformance results and summarises them in a table (bot AES and DC) in an out file