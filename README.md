# Deepcopy & AES Benchmarking Repo

## Repository Contents
- **pyperformance (local copy)**  
  Contains a forked version of the `pyperformance` benchmark suite, including edited benchmark definitions and optimized versions of Python libraries (`copy.py`, AES routines).  
- **run.sh**  
  A driver script that installs prerequisites, runs all benchmarks, collects profiling data, and exports comparisons. It automates:  
  - AES benchmark runs (baseline vs optimized) with `perf stat`, `perf report`, and `py-spy` flamegraphs.  
  - Deepcopy benchmark runs (baseline vs optimized) with the same set of tools.  
  - Parsing and exporting results to CSV for statistical and performance comparison.  
- **res/**  
  Output directory where all benchmark results are stored, including raw logs, flamegraphs (`.svg`), perf reports, and CSV comparisons.  
- **Python parsing scripts**  
  Utility scripts (`parse_perf_stat_compare.py`, `parse_pyperf_results.py`) that process raw `perf` and benchmark output into CSVs for easier analysis and plotting.  

## How to Run
1. **Clone the repository** to your local workspace.  
2. **Prepare your environment**:  
   - Ensure Python 3 is installed and optionally create a `venv`.  
   - Update Linux tools and install `perf` (required for low-level profiling).  
3. **Make the run script executable**:  
   ```bash
   chmod +x run.sh
   ./run.sh
   ```  
   The script will:  
   - Install required Python packages (`pyperformance`, `pyperf`, `py-spy`, `pyaes`, etc.).  
   - Clone Brendan Gregg’s **FlameGraph** utilities if not already present.  
   - Run **AES benchmarks**:  
     - Baseline vs optimized runs using `bm_crypto_pyaes`.  
     - Collect `perf stat` metrics, `perf report` call graphs, and flamegraphs.  
     - Export results as CSVs for side-by-side comparison.  
   - Run **Deepcopy benchmarks**:  
     - Baseline vs optimized runs using `bm_deepcopy`.  
     - Collect `perf stat` metrics, `perf report` call graphs, and flamegraphs.  
     - Export results as CSVs for side-by-side comparison.  

## Results
All results are saved in the `res/` directory, organized by benchmark:  
- `res/aes/` contains AES benchmark results (`perf_stat_aes_*`, flamegraphs, and CSV comparisons).  
- `res/dc/` contains deepcopy benchmark results (`perf_stat_dc_*`, flamegraphs, and CSV comparisons).  

Each subdirectory includes:  
- **perf_stat_*.txt** – raw performance counter statistics.  
- **perf_report_*.txt** – detailed call-graph reports from `perf`.  
- **flamegraph_*.svg** – interactive flamegraphs generated via `py-spy`.  
- **pyperformance_*_compare.csv** – processed comparisons of baseline vs optimized runs.  
