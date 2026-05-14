# CVRP Algorithm Comparison Experiment

## 1. Overview

This experiment benchmarks 5 AILS2 algorithm variants independently on CVRP instances. Unlike the competition pipeline (`SISR/main_for_all_final.py`), algorithms do **not** share a solution database. Each algorithm runs in isolation and its convergence profile is recorded for paper analysis.

---

## 2. Pipeline

1. **Set instances and initial solutions**
   - Place instance files in `Experiment/Instances/{instance_name}.vrp`
   - Place initial solution files in `Experiment/Initial_sols/{instance_name}/time1.sol`, `time2.sol`, etc.
   - Each `(instance, initial_solution)` pair is one **trial**.

2. **Run algorithms in parallel, record profiles**
   - For each trial, all 5 algorithm variants (or, a selected list of algorithm variants) are launched as independent subprocesses simultaneously.
   - Each algorithm gets its own temporary SQLite DB (pre-populated with the initial solution).
   - When each trial finish, Python polls the DB to collect `(algorithm_name, timestamp_sec, score)` data points.
   - After the time limit, all subprocesses are killed.

3. **Store results**
   - Results are appended to `Experiment/results/{experiment_name}.csv` after each trial.

---

## 3. Algorithm Variants

| Alias | JAR location (from repo root) |
|---|---|
| `AILS2` | `AILS2/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar` |
| `AILS2_Eoh_Acc` | `AILS2_Eoh_Acc/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar` |
| `AILS2_Eoh_Acc_large` | `AILS2_Eoh_Acc_large/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar` |
| `AILS2_Eoh_Omega2` | `AILS2_Eoh_Omega2/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar` |
| `AILS2_Eoh_Ruin` | `AILS2_Eoh_Ruin/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar` |

All variants share the same CLI interface (`SearchMethod.AILSII` main class, same `InputParameters.java`).

---

## 4. Configuration (in `run_experiment.py`)

All experiment settings are defined at the top of the script:

```python
EXPERIMENT_NAME   = "baseline"   # used in output filename
TIME_LIMIT_SEC    = 3600         # 1 hour per algorithm run
UPDATE_INTERVAL   = 60           # seconds between DB polls
D_MAX             = 30
D_MIN             = 15
GAMMA             = 30
VARPHI            = 40
ETA_MAX           = 1.0          # can be a dict keyed by algo name if variants 
INSTANCES         = ["instance_name.vrp",] # a list of instance filenames
INITIAL_SOLS      = ["20260112_235936.sol",] # a list of initial solutions, named with timestamp
```

The output filename is auto-generated as:
```
results/{EXPERIMENT_NAME}.csv
```

---

## 5. Output CSV Format

Each algorithm gets its own CSV file per trial:

`Experiment/results/{experiment_name}/{instance}__{init_sol}__{algo}.csv`

| Column | Description |
|---|---|
| `timestamp_sec` | Elapsed seconds since start of this algorithm's run |
| `score` | Best solution cost found at that timestamp |

Example file `results/baseline/XL-n1048-k237__20260112_235936__AILS2.csv`:
```
timestamp_sec,score
12.3,27591.0
45.1,27480.5
```

Skip logic: if the output file already exists, delete the output file and re-run.

To aggregate all results in pandas:
```python
import pandas as pd
from pathlib import Path

dfs = []
for f in Path("results/baseline").glob("*.csv"):
    instance, init_sol, algo = f.stem.split("__")
    df = pd.read_csv(f)
    df["instance"] = instance
    df["initial_sol"] = init_sol
    df["algo"] = algo
    dfs.append(df)
all_results = pd.concat(dfs)
```

Read DB after process finishes, and read the full solution_history table and dump it to CSV.

---

## 6. Folder Structure

```
Experiment/
  EXPERIMENT.md              ← this file
  run_experiment.py          ← entry point
  Instances/
    {instance_name}.vrp
  Initial_sols/
    {instance_name}/
      time1.sol
      time2.sol
      ...
  results/
    {experiment_name}@{hyperparams}.csv
  tmp/                       ← auto-created, auto-cleaned temp DBs
```

---

## 7. How to Run

```bash
# 1. Compile all algorithms (from repo root)
cd SISR && bash compile.sh && cd ..

# 2. Place instances and initial solutions (see folder structure above)

# 3. Run the experiment
python Experiment/run_experiment.py

# 4. (Optional) modify settings at top of run_experiment.py before running
```

---

## 8. Implementation Notes

- **Initial solution loading:** Java's `AILSII.search()` calls `SQLiteHelper.loadBest(sharedDB)` at startup to optionally load a warm-start solution. We pre-populate each algorithm's private temp DB with the initial solution before launching the process.
- **Initial solution file format:** Each `.sol` file contains a flat list of node indices (the route representation used by the Java solution class), one integer per line or space-separated.
- **Process management:** Uses Python `multiprocessing` (spawn mode) + `psutil` for clean process-tree teardown, consistent with `main_for_all_final.py`.
- **Parallelism:** Within each trial, all 5 algorithms run concurrently. Trials themselves run sequentially to avoid resource contention.
