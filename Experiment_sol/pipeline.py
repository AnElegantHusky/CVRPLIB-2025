"""
pipeline.py — Experiment pipeline using file-version JARs.

Steps:
  1. Compile all variants (runs src/compile.sh — skippable with --no-compile).
  2. Run AILS2 on assigned instances in parallel.
     - results/AILS2/{instance}.csv + results/AILS2/{instance}.sol
     - .sol is also copied to Initial_sols/{instance}.sol for step 3
  3. Run all variants on the same instances using the step-2 .sol as warm start.
     - results/{algo}/{instance}.csv + results/{algo}/{instance}.sol

Usage:
    python pipeline.py [--time-limit SEC] [--index-start N] [--index-end M] [--eta-max F]
                       [--no-compile]
"""

import argparse
import multiprocessing
import shutil
import subprocess
import sys
from pathlib import Path

from test_one_run import (
    ALGO_JARS,
    DEFAULT_CONFIG,
    EXPERIMENT_DIR,
    ROOT_DIR,
    run_single,
)

# ─── Constants ────────────────────────────────────────────────────────────────

INSTANCES_DIR = EXPERIMENT_DIR / "Instances"
INIT_SOLS_DIR = EXPERIMENT_DIR / "Initial_sols"
RESULTS_DIR   = EXPERIMENT_DIR / "results"

STEP2_ALGO  = "AILS2"
STEP3_ALGOS = ["AILS2_Eoh_Acc", "AILS2_Eoh_Acc_large", "AILS2_Eoh_Omega2", "AILS2_Eoh_Ruin", "AILS2_ws"]

# ─── Step 1: Compile ──────────────────────────────────────────────────────────

def compile_algos() -> bool:
    compile_sh = ROOT_DIR / "src" / "compile.sh"
    print("\n" + "="*60)
    print("Step 1: Compiling file-version algorithms")
    print("="*60)
    result = subprocess.run(["bash", str(compile_sh)], cwd=str(ROOT_DIR))
    if result.returncode != 0:
        print("[Error] Compilation failed.", file=sys.stderr)
        return False
    print("[Step 1] Compilation done.")
    return True


# ─── Step-2 worker ────────────────────────────────────────────────────────────

def _step2_worker(args):
    instance, cfg = args
    out_dir = RESULTS_DIR / STEP2_ALGO
    try:
        run_single(
            algo=STEP2_ALGO,
            instance=instance,
            init_sol=None,
            output_dir=out_dir,
            cfg=cfg,
            verbose=False,
        )
        sol = out_dir / f"{instance.stem}.sol"
        if sol.exists():
            INIT_SOLS_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(sol), str(INIT_SOLS_DIR / sol.name))
            return (instance.stem, INIT_SOLS_DIR / sol.name)
        else:
            print(f"  [Warning] No .sol produced for {instance.stem}", file=sys.stderr)
            return (instance.stem, None)
    except Exception as e:
        print(f"  [Error] step2 {instance.stem}: {e}", file=sys.stderr)
        return (instance.stem, None)


# ─── Step-3 worker ────────────────────────────────────────────────────────────

def _step3_worker(args):
    algo, instance, init_sol, cfg = args
    out_dir = RESULTS_DIR / algo
    try:
        run_single(
            algo=algo,
            instance=instance,
            init_sol=init_sol,
            output_dir=out_dir,
            cfg=cfg,
            verbose=False,
        )
        return (algo, instance.stem, "ok")
    except Exception as e:
        return (algo, instance.stem, f"error: {e}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(time_limit: int, index_start: int, index_end: int | None,
                 eta_max: float = 1.0, no_compile: bool = False):
    all_instances = sorted(INSTANCES_DIR.glob("*.vrp"))
    if not all_instances:
        print(f"[Error] No .vrp files in {INSTANCES_DIR}", file=sys.stderr)
        sys.exit(1)

    instances = all_instances[index_start:index_end]
    if not instances:
        print(f"[Error] Empty instance slice [{index_start}:{index_end}]", file=sys.stderr)
        sys.exit(1)

    cfg_step2 = {**DEFAULT_CONFIG, "time_limit_sec": time_limit, "eta_max": 1.0}
    cfg_step3 = {**DEFAULT_CONFIG, "time_limit_sec": time_limit, "eta_max": eta_max}

    print(f"\nPipeline config:")
    print(f"  instances   : [{index_start}:{index_end}] ({len(instances)} total)")
    print(f"  time_limit  : {time_limit}s")
    print(f"  step2 algo  : {STEP2_ALGO}  eta_max=1.0")
    print(f"  step3 algos : {STEP3_ALGOS}  eta_max={eta_max}")

    # ── Step 1 ──
    if not no_compile:
        if not compile_algos():
            sys.exit(1)
    else:
        print("\n[Step 1] Skipped (--no-compile).")

    # ── Step 2: AILS2 baseline ──
    print("\n" + "="*60)
    print("Step 2: AILS2 — generating initial solutions")
    print("="*60)

    step2_args = [(inst, cfg_step2) for inst in instances]
    with multiprocessing.Pool(processes=len(instances)) as pool:
        step2_results = pool.map(_step2_worker, step2_args)

    sol_map = {}
    for stem, sol_path in step2_results:
        if sol_path:
            sol_map[stem] = sol_path
        else:
            print(f"  [Warning] No solution for {stem}", file=sys.stderr)

    print(f"[Step 2] Done. {len(sol_map)}/{len(instances)} solutions in {INIT_SOLS_DIR}")

    # ── Step 3: All variants with warm start ──
    print("\n" + "="*60)
    print("Step 3: Running all variants with initial solutions")
    print("="*60)

    step3_args = []
    for inst in instances:
        init_sol = sol_map.get(inst.stem)
        if init_sol is None:
            print(f"  [Skip] {inst.stem} — no step-2 solution", file=sys.stderr)
            continue
        for algo in STEP3_ALGOS:
            if not ALGO_JARS[algo].exists():
                print(f"  [Skip] {algo} JAR not found", file=sys.stderr)
                continue
            step3_args.append((algo, inst, init_sol, cfg_step3))

    print(f"  Launching {len(step3_args)} jobs in parallel ...")
    with multiprocessing.Pool(processes=len(step3_args)) as pool:
        step3_results = pool.map(_step3_worker, step3_args)

    for algo, stem, status in step3_results:
        print(f"  [Done] {algo} × {stem}: {status}")

    print("\nPipeline complete.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="CVRP file-version experiment pipeline.")
    p.add_argument("--time-limit",  type=int,   default=86400, dest="time_limit",
                   help="seconds per run (default: 86400)")
    p.add_argument("--index-start", type=int,   default=0,     dest="index_start",
                   help="first instance index, 0-based inclusive (default: 0)")
    p.add_argument("--index-end",   type=int,   default=None,  dest="index_end",
                   help="last instance index, 0-based exclusive (default: all)")
    p.add_argument("--eta-max",     type=float, default=DEFAULT_CONFIG["eta_max"], dest="eta_max",
                   help=f"etaMax for step 3 (default: {DEFAULT_CONFIG['eta_max']})")
    p.add_argument("--no-compile",  action="store_true", default=False, dest="no_compile",
                   help="skip step 1 compilation")
    return p.parse_args()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    args = parse_args()
    run_pipeline(
        time_limit=args.time_limit,
        index_start=args.index_start,
        index_end=args.index_end,
        eta_max=args.eta_max,
        no_compile=args.no_compile,
    )
