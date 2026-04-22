"""
pipeline.py — Full experiment pipeline for multi-server deployment.

Steps:
  1. Compile all 5 AILS2 variants.
  2. Run AILS2 on assigned instances; save best solution as .sol in
     results/AILS2_1day_solution/{instance}.sol
  3. Run remaining 4 algorithms on the same instances using step-2 .sol
     as initial solution; save convergence CSVs in results/{algo}/

Usage:
    python pipeline.py [--time-limit SEC] [--index-start N] [--index-end M]

    --time-limit   : seconds per run for both step 2 and step 3 (default 86400)
    --index-start  : first instance index (0-based, inclusive, default 0)
    --index-end    : last  instance index (0-based, exclusive, default all)

Example (server 0 handles first 10 instances, 1-hour test):
    python pipeline.py --time-limit 3600 --index-start 0 --index-end 10
"""

import argparse
import ast
import multiprocessing
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

from test_one_run import (
    ALGO_JARS,
    DEFAULT_CONFIG,
    EXPERIMENT_DIR,
    ROOT_DIR,
    init_db,
    preload_init_solution,
    build_cmd,
    read_history,
    kill_tree,
    run_single,
)

import time

# ─── Constants ────────────────────────────────────────────────────────────────

INSTANCES_DIR   = EXPERIMENT_DIR / "Instances"
INIT_SOLS_DIR   = EXPERIMENT_DIR / "Initial_sols"
RESULTS_DIR     = EXPERIMENT_DIR / "results"
TMP_DIR         = EXPERIMENT_DIR / "tmp"

STEP2_ALGO      = "AILS2"
STEP2_RESULTS   = RESULTS_DIR / "AILS2_1day_solution"
STEP3_ALGOS     = ["AILS2_Eoh_Acc", "AILS2_Eoh_Acc_large", "AILS2_Eoh_Omega2", "AILS2_Eoh_Ruin", "AILS2"]

# ─── Step 1: Compile ──────────────────────────────────────────────────────────

def compile_algos() -> bool:
    """Run SISR/compile.sh from the repo root. Returns True on success."""
    compile_sh = ROOT_DIR / "SISR" / "compile.sh"
    print("\n" + "="*60)
    print("Step 1: Compiling algorithms")
    print("="*60)
    result = subprocess.run(
        ["bash", str(compile_sh)],
        cwd=str(ROOT_DIR),
    )
    if result.returncode != 0:
        print("[Error] Compilation failed.", file=sys.stderr)
        return False
    print("[Step 1] Compilation done.")
    return True


# ─── DB → .sol helper ─────────────────────────────────────────────────────────

def db_to_sol(db_path: Path, sol_path: Path) -> bool:
    """Read global_best from db_path and write a .sol file to sol_path."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            row = conn.execute(
                "SELECT solution, score FROM global_best WHERE id=1"
            ).fetchone()
    except sqlite3.Error as e:
        print(f"[DB Error] {e}", file=sys.stderr)
        return False

    if not row or not row[0]:
        print(f"[Warning] No solution in {db_path}", file=sys.stderr)
        return False

    solution_text, score = row
    try:
        routes = ast.literal_eval(solution_text)
    except Exception:
        try:
            import json
            routes = json.loads(solution_text)
        except Exception as e:
            print(f"[Parse Error] {e}", file=sys.stderr)
            return False

    sol_path.parent.mkdir(parents=True, exist_ok=True)
    with open(sol_path, "w", newline="", encoding="utf-8") as f:
        for i, route in enumerate(routes):
            f.write(f"Route #{i+1}: {' '.join(map(str, route))}\n")
        f.write(f"Cost {score:.6f}\n")

    print(f"  [Sol] Written: {sol_path.name}  cost={score:.2f}  routes={len(routes)}")
    return True


# ─── Step-2 worker (one instance) ─────────────────────────────────────────────

def _step2_worker(args):
    instance, cfg = args
    algo = STEP2_ALGO
    jar  = ALGO_JARS[algo]

    TMP_DIR.mkdir(exist_ok=True)
    db_path = TMP_DIR / f"step2__{instance.stem}__{algo}.db"
    for suffix in ["", "-wal", "-shm"]:
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()

    init_db(db_path)

    start_time = time.time()
    cmd = build_cmd(jar, instance, db_path, start_time, cfg)
    print(f"  [Step2] Running {algo} on {instance.name} ...")

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        proc.wait(timeout=cfg["time_limit_sec"] + 30)
    except subprocess.TimeoutExpired:
        kill_tree(proc.pid)
        proc.wait()

    stderr_out = proc.stderr.read() if proc.stderr else ""
    if stderr_out:
        print(f"[stderr {instance.stem}]\n{stderr_out}", file=sys.stderr)

    sol_path = STEP2_RESULTS / f"{instance.stem}.sol"
    ok = db_to_sol(db_path, sol_path)
    if ok:
        for suffix in ["", "-wal", "-shm"]:
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()
    return (instance.stem, sol_path if ok else None)


# ─── Step-3 worker (one algo × instance) ──────────────────────────────────────

def _step3_worker(args):
    algo, instance, init_sol, cfg = args
    out_csv = RESULTS_DIR / algo / f"{instance.stem}.csv"
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    try:
        run_single(algo=algo, instance=instance, init_sol=init_sol,
                   output_csv=out_csv, cfg=cfg, verbose=False)
        db_path = TMP_DIR / f"{out_csv.stem}.db"
        for suffix in ["", "-wal", "-shm"]:
            p = Path(str(db_path) + suffix)
            if p.exists():
                p.unlink()
        return (algo, instance.stem, "ok")
    except Exception as e:
        return (algo, instance.stem, f"error: {e}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(time_limit: int, index_start: int, index_end: int | None, eta_max: float = DEFAULT_CONFIG["eta_max"]):
    # ── Discover instances ──
    all_instances = sorted(INSTANCES_DIR.glob("*.vrp"))
    if not all_instances:
        print(f"[Error] No .vrp files in {INSTANCES_DIR}", file=sys.stderr)
        sys.exit(1)

    instances = all_instances[index_start:index_end]
    if not instances:
        print(f"[Error] Empty instance slice [{index_start}:{index_end}] "
              f"(total={len(all_instances)})", file=sys.stderr)
        sys.exit(1)

    cfg_step2 = {**DEFAULT_CONFIG, "time_limit_sec": time_limit, "eta_max": 1.0}
    cfg_step3 = {**DEFAULT_CONFIG, "time_limit_sec": time_limit, "eta_max": eta_max}

    print(f"\nPipeline config:")
    print(f"  instances   : {index_start}..{index_end or len(all_instances)-1} "
          f"({len(instances)} total)")
    print(f"  time_limit  : {time_limit}s")
    print(f"  step2 algo  : {STEP2_ALGO}  eta_max=1.0")
    print(f"  step3 algos : {STEP3_ALGOS}  eta_max={eta_max}")

    # ── Step 1: Compile ──
    if not compile_algos():
        sys.exit(1)

    # ── Step 2: AILS2 on all assigned instances (parallel) ──
    print("\n" + "="*60)
    print("Step 2: AILS2 — generating initial solutions")
    print("="*60)
    STEP2_RESULTS.mkdir(parents=True, exist_ok=True)

    step2_args = [(inst, cfg_step2) for inst in instances if ALGO_JARS[STEP2_ALGO].exists()]
    with multiprocessing.Pool(processes=len(step2_args)) as pool:
        step2_results = pool.map(_step2_worker, step2_args)

    sol_map = {}  # instance_stem → sol_path
    for stem, sol_path in step2_results:
        if sol_path:
            sol_map[stem] = sol_path
        else:
            print(f"  [Warning] No solution produced for {stem}", file=sys.stderr)

    print(f"[Step 2] Done. {len(sol_map)}/{len(instances)} solutions written.")

    # ── Step 3: Remaining algos using step-2 .sol as init ──
    print("\n" + "="*60)
    print("Step 3: Running remaining algorithms")
    print("="*60)

    # Clean output dirs for this run
    for algo in STEP3_ALGOS:
        algo_dir = RESULTS_DIR / algo
        if algo_dir.exists():
            shutil.rmtree(algo_dir)
        algo_dir.mkdir(parents=True)

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

    print(f"  Launching {len(step3_args)} jobs (all in parallel) ...")
    with multiprocessing.Pool(processes=len(step3_args)) as pool:
        step3_results = pool.map(_step3_worker, step3_args)

    for algo, stem, status in step3_results:
        print(f"  [Done] {algo} × {stem}: {status}")

    print("\nPipeline complete.")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="CVRP experiment pipeline.")
    p.add_argument("--time-limit",   type=int,   default=86400,                      dest="time_limit",
                   help="seconds per run for step 2 and step 3 (default: 86400)")
    p.add_argument("--index-start",  type=int,   default=0,                          dest="index_start",
                   help="first instance index, 0-based inclusive (default: 0)")
    p.add_argument("--index-end",    type=int,   default=None,                       dest="index_end",
                   help="last instance index, 0-based exclusive (default: all)")
    p.add_argument("--eta-max",      type=float, default=DEFAULT_CONFIG["eta_max"],  dest="eta_max",
                   help=f"etaMax passed to Java (default: {DEFAULT_CONFIG['eta_max']})")
    return p.parse_args()


if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    args = parse_args()
    run_pipeline(
        time_limit=args.time_limit,
        index_start=args.index_start,
        index_end=args.index_end,
        eta_max=args.eta_max,
    )
