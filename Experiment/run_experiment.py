"""
run_experiment.py — Run multiple experiments sequentially.

Each experiment is defined as a dict in the EXPERIMENTS list at the bottom of this file.
Within each trial (instance × init_sol × run_id), algos are dispatched through a
pool of size `max_parallel`. Set max_parallel=1 for pure sequential (each algo gets
the full CPU); set it higher to trade CPU sharing for wall-clock speed.

Output: results/{experiment_name}/{instance}__{init_sol}__{algo}__run{n}.csv
        Each CSV has two columns: timestamp_sec, score.

Rerun behaviour: the entire results/{experiment_name}/ folder is deleted at the
start of the experiment, so results are always fresh.

Usage:
    python run_experiment.py
"""

import multiprocessing
import shutil
import sys
from pathlib import Path

from test_one_run import (
    ALGO_JARS,
    DEFAULT_CONFIG,
    EXPERIMENT_DIR,
    run_single,
)

# ─── Experiment definitions ───────────────────────────────────────────────────
# Fields:
#   name         : output folder → results/{name}/
#   algos        : list of algo names (keys of ALGO_JARS); None = all
#   instances    : list of instance filenames in Instances/; None = all .vrp files
#   initial_sols : list of .sol filenames (same set for all instances); None = all per instance
#   n_runs       : how many independent runs per (algo, instance, init_sol) triple
#   max_parallel : max algos running simultaneously (1 = sequential, None = all at once)
#   cfg          : hyperparameter overrides (merged with DEFAULT_CONFIG)

    # cfg = {
    #         "time_limit_sec":  args.time_limit,
    #         "d_max":           args.d_max,
    #         "d_min":           args.d_min,
    #         "gamma":           args.gamma,
    #         "varphi":          args.varphi,
    #         "eta_max":         args.eta_max,
    #     }

EXPERIMENTS = [
    # {
    #     "name":         "baseline",
    #     "algos":        None,   # all
    #     "instances":    None,   # all .vrp in Instances/
    #     "initial_sols": None,   # all .sol per instance
    #     "n_runs":       1,
    #     "cfg":          {},
    # },
    
    # Example — short smoke test:
    # {
    #     "name":         "short",
    #     "algos":        ["AILS2", "AILS2_Eoh_Omega2", "AILS2_Eoh_Ruin", "AILS2_Eoh_Acc"],
    #     "instances":    ["XL-n1048-k237.vrp"],
    #     "initial_sols": ["20260112_235936.sol"],
    #     "n_runs":       3,
    #     "max_parallel": 3,
    #     "cfg":          {"time_limit_sec": 3600, "eta_max": 0.01},
    # },
    
    # Example — large instance test:
    # {
    #     "name":         "Cust=large_eta=0.01",
    #     "algos":        ["AILS2", "AILS2_Eoh_Omega2", "AILS2_Eoh_Ruin", "AILS2_Eoh_Acc"],
    #     "instances":    ["XL-n10001-k1570.vrp"],
    #     "initial_sols": ["20260112_235936.sol"],
    #     "n_runs":       3,
    #     "max_parallel": 6,
    #     "cfg":          {"time_limit_sec": 3600, "eta_max": 0.01},
    # },
    
    # {
    #     "name":         "Cust=large_eta=0.5",
    #     "algos":        ["AILS2_Eoh_Ruin", "AILS2"],
    #     "instances":    ["XL-n10001-k1570.vrp"],
    #     "initial_sols": ["20260112_235936.sol"],
    #     "n_runs":       3,
    #     "max_parallel": 3,
    #     "cfg":          {"time_limit_sec": 4 * 3600, "eta_max": 0.5},
    # },
    
    {
        "name":         "Cust=select_eta=0.5",
        "algos":        ["AILS2_Eoh_Ruin", "AILS2"],
        "instances":    [
            # "XL-n1048-k237.vrp",
            # "XL-n1654-k11.vrp",
            # "XL-n2401-k408.vrp",
            # "XL-n3194-k161.vrp",
            "XL-n3888-k1010.vrp",
            "XL-n4635-k790.vrp",
            "XL-n5288-k1246.vrp",
            # "XL-n6034-k61.vrp",
            # "XL-n10001-k1570.vrp"
        ],
        "initial_sols": ["20260112_235936.sol"],
        "n_runs":       1,
        "max_parallel": 6,
        "cfg":          {"time_limit_sec": 24 * 3600, "eta_max": 0.5},
    },
]

# ─── Discovery helpers ────────────────────────────────────────────────────────

def resolve_instances(instances_cfg):
    instances_dir = EXPERIMENT_DIR / "Instances"
    if instances_cfg is None:
        paths = sorted(instances_dir.glob("*.vrp"))
        if not paths:
            print(f"[Warning] No .vrp files in {instances_dir}", file=sys.stderr)
        return paths
    return [instances_dir / name for name in instances_cfg]


def resolve_init_sols(instance, initial_sols_cfg):
    sol_dir = EXPERIMENT_DIR / "Initial_sols" / instance.stem
    if not sol_dir.exists():
        print(f"[Warning] No initial solutions folder: {sol_dir}", file=sys.stderr)
        return []
    if initial_sols_cfg is None:
        return sorted(sol_dir.glob("*.sol"))
    return [sol_dir / name for name in initial_sols_cfg]


def resolve_algos(algos_cfg):
    if algos_cfg is None:
        return list(ALGO_JARS.keys())
    return algos_cfg


# ─── Parallel worker ──────────────────────────────────────────────────────────

def _worker(args):
    """Call run_single in a subprocess-pool worker."""
    algo, instance, init_sol, output_csv, cfg = args
    try:
        run_single(algo=algo, instance=instance, init_sol=init_sol,
                   output_csv=output_csv, cfg=cfg, verbose=False)
        return (algo, output_csv.name, "ok")
    except Exception as e:
        return (algo, output_csv.name, f"error: {e}")


# ─── Experiment runner ────────────────────────────────────────────────────────

def run_experiment(exp):
    name         = exp["name"]
    n_runs       = exp.get("n_runs", 1)
    max_parallel = exp.get("max_parallel", 1)
    algos        = resolve_algos(exp.get("algos"))
    cfg          = {**DEFAULT_CONFIG, **exp.get("cfg", {})}

    results_dir = EXPERIMENT_DIR / "results" / name

    # Always start fresh — delete the whole results folder for this experiment
    if results_dir.exists():
        shutil.rmtree(results_dir)
        print(f"[Clean] Removed existing {results_dir}")
    results_dir.mkdir(parents=True)

    instances = resolve_instances(exp.get("instances"))
    if not instances:
        print(f"[Experiment '{name}'] No instances found, skipping.")
        return

    print(f"\n{'='*60}")
    print(f"Experiment   : {name}")
    print(f"Output       : {results_dir}")
    print(f"Algos        : {algos}")
    print(f"Instances    : {[i.name for i in instances]}")
    print(f"n_runs       : {n_runs}")
    print(f"max_parallel : {max_parallel}")
    print(f"Config       : {cfg}")
    print(f"{'='*60}")

    trial_num = 0
    for instance in instances:
        init_sols = resolve_init_sols(instance, exp.get("initial_sols"))
        for init_sol in init_sols:
            for run_id in range(1, n_runs + 1):
                trial_num += 1
                run_tag = f"run{run_id:02d}"
                print(f"\n[Trial {trial_num}] {instance.stem} × {init_sol.name} × {run_tag}")

                worker_args = []
                for algo in algos:
                    if not ALGO_JARS[algo].exists():
                        print(f"  [Skip] {algo} — JAR not found", file=sys.stderr)
                        continue
                    out_csv = results_dir / f"{instance.stem}__{init_sol.stem}__{algo}__{run_tag}.csv"
                    worker_args.append((algo, instance, init_sol, out_csv, cfg))

                if not worker_args:
                    continue

                n_workers = min(max_parallel, len(worker_args)) if max_parallel else len(worker_args)
                print(f"  [Launch] {[a[0] for a in worker_args]} (max_parallel={n_workers}) ...")
                with multiprocessing.Pool(processes=n_workers) as pool:
                    results = pool.map(_worker, worker_args)

                for algo_name, _, status in results:
                    print(f"  [Done] {algo_name}: {status}")

    print(f"\n[Experiment '{name}' complete] {trial_num} trial(s) processed.")


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    for exp in EXPERIMENTS:
        run_experiment(exp)
    print("\nAll experiments done.")
