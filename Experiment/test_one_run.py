"""
test_one_run.py — Run a single (algo, instance, initial_solution) trial and output a CSV profile.

Usage:
    python test_one_run.py \
        --algo AILS2 \
        --instance Instances/X-n101-k25.vrp \
        --init-sol Initial_sols/X-n101-k25/time1.sol \
        --output results/test.csv

Modular design: each function is reusable by run_experiment.py.
"""

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
import time
import threading
import os
from pathlib import Path

import psutil
import vrplib

# ─── Paths ────────────────────────────────────────────────────────────────────

EXPERIMENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = EXPERIMENT_DIR.parent

ALGO_JARS = {
    "AILS2":              ROOT_DIR / "AILS2"              / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
    "AILS2_Eoh_Acc":      ROOT_DIR / "AILS2_Eoh_Acc"      / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
    "AILS2_Eoh_Acc_large":ROOT_DIR / "AILS2_Eoh_Acc_large"/ "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
    "AILS2_Eoh_Omega2":   ROOT_DIR / "AILS2_Eoh_Omega2"   / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
    "AILS2_Eoh_Ruin":     ROOT_DIR / "AILS2_Eoh_Ruin"     / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
}

# ─── Config (override via CLI args or edit here) ──────────────────────────────

DEFAULT_CONFIG = {
    "time_limit_sec": 3600,
    "d_max": 30,
    "d_min": 15,
    "gamma": 30,
    "varphi": 40,
    "eta_max": 1.0,
}

# ─── DB helpers ───────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> None:
    """Create the SQLite DB schema expected by the Java code."""
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            if os.path.exists(db_path / "-wal"): os.remove(db_path / "-wal")
            if os.path.exists(db_path / "-shm"): os.remove(db_path / "-shm")
        except OSError as e:
            print(f"[DB Init Warning] Failed to delete old DB: {e}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=30000;")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS global_best (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                score REAL,
                solution TEXT,
                algo_name TEXT,
                runningtime REAL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO global_best (id, score, solution, algo_name, runningtime)
            VALUES (1, 1e20, '', '', 0)
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS solution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                algo_name TEXT,
                score REAL,
                solution TEXT,
                runningtime REAL
            )
        """)
        
        conn.commit()
        # conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    finally:
        conn.close()


def preload_init_solution(db_path: Path, sol_path: Path) -> None:
    """Pre-populate global_best with the initial solution so Java picks it up at startup.
    Uses vrplib to parse the .sol file, extracting both routes and the real cost.
    """
    sol = vrplib.read_solution(str(sol_path))
    routes = sol['routes']   # list of lists, e.g. [[1,2,3],[4,5]]
    cost = sol['cost']
    sol_json = json.dumps(routes)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("""
            UPDATE global_best SET score=?, solution=?, algo_name='init', runningtime=0
            WHERE id=1
        """, (cost, sol_json))
        conn.commit()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    finally:
        conn.close()


def read_history(db_path: Path) -> list[tuple[float, float]]:
    """Read all (runningtime, score) rows from solution_history, ordered by time."""
    try:
        with sqlite3.connect(str(db_path)) as conn:
            rows = conn.execute(
                "SELECT runningtime, score FROM solution_history ORDER BY runningtime"
            ).fetchall()
        return [(r[0], r[1]) for r in rows]
    except sqlite3.Error as e:
        print(f"[DB read error] {e}", file=sys.stderr)
        return []


# ─── Process helpers ──────────────────────────────────────────────────────────

def build_cmd(jar: Path, instance: Path, db: Path,
              start_time: float, cfg: dict) -> list[str]:
    """Build the java -jar command for one algorithm."""
    return [
        "java", "--enable-native-access=ALL-UNNAMED", 
        # "-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address=*:5005",
        "-jar",              str(jar),
        "-file",             str(instance.resolve()),
        "-sharedDB",         str(db.resolve()),
        "-rounded",          "true",
        "-best",             "0",
        "-limit",            str(cfg["time_limit_sec"]),
        "-crtRunningTime",   "0",
        "-stoppingCriterion","Time",
        "-dMax",             str(cfg["d_max"]),
        "-dMin",             str(cfg["d_min"]),
        "-gamma",            str(cfg["gamma"]),
        "-varphi",           str(cfg["varphi"]),
        "-startTime",        str(start_time),
        "-etaMax",           str(cfg["eta_max"]),
        
    ]


def kill_tree(pid: int) -> None:
    """Kill a process and all its children."""
    try:
        parent = psutil.Process(pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except psutil.NoSuchProcess:
        pass


# ─── Trial runner ─────────────────────────────────────────────────────────────

def run_single(algo: str, instance: Path, init_sol: Path | None,
               output_csv: Path, cfg: dict, verbose: bool = False) -> None:
    """
    Run one (algo, instance, init_sol) trial:
      1. Set up a private temp DB, optionally pre-populated with init_sol.
      2. Launch the Java process.
      3. Wait for it to finish (or kill after time limit).
      4. Read solution_history from DB and write to CSV.

    init_sol: if None, algorithm constructs its own initial solution.
    verbose: if True, stream Java stdout line-by-line (shows improvements as they happen).
    """
    jar = ALGO_JARS[algo]
    if not jar.exists():
        print(f"[Error] JAR not found: {jar}", file=sys.stderr)
        sys.exit(1)

    # Temp DB for this run — always start fresh.
    # Name is derived from output_csv so parallel runs with different run_ids
    # never share a DB even if they happen to run concurrently.
    tmp_dir = EXPERIMENT_DIR / "tmp"
    tmp_dir.mkdir(exist_ok=True)
    db_path = tmp_dir / f"{output_csv.stem}.db"
    for suffix in ["", "-wal", "-shm"]:
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()

    print(f"[Setup] instance={instance.name}  init_sol={init_sol.name if init_sol else 'None'}  algo={algo}")

    print("[Debug] Cleaning up old DB files...")
    init_db(db_path)
    print("[Debug] init_db done")
    if init_sol is not None:
        preload_init_solution(db_path, init_sol)
        print("[Debug] preload_init_solution done")
    else:
        print("[Debug] no init_sol, algorithm will construct its own")

    start_time = time.time()
    cmd = build_cmd(jar, instance, db_path, start_time, cfg)
    print(f"[Run]   {' '.join(cmd)}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)
    print(f"[Debug] Process started, pid={proc.pid}")

    def drain_stdout(p, prefix, do_print):
        if p.stdout:
            for line in p.stdout:
                if do_print:
                    print(f"[{prefix}] {line}", end="", flush=True)
        print(f"[Debug] stdout drain finished for {prefix}")

    stdout_thread = threading.Thread(target=drain_stdout,
                                     args=(proc, algo, verbose), daemon=True)
    stdout_thread.start()
    print(f"[Debug] stdout thread started, waiting for process (timeout={cfg['time_limit_sec']+10}s)...")

    try:
        proc.wait(timeout=cfg["time_limit_sec"] + 10)
        print(f"[Debug] proc.wait() returned, returncode={proc.returncode}")
    except subprocess.TimeoutExpired:
        print(f"[Timeout] killing {algo}")
        kill_tree(proc.pid)
        proc.wait()
        print(f"[Debug] process killed")

    print("[Debug] joining stdout thread...")
    stdout_thread.join(timeout=5)
    print("[Debug] stdout thread joined")

    stderr_out = proc.stderr.read() if proc.stderr else ""
    if stderr_out:
        print(f"[stderr]\n{stderr_out}", file=sys.stderr)

    # Collect results
    history = read_history(db_path)
    print(f"[Done]  {len(history)} improvement records found")

    # Write CSV
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_sec", "score"])
        writer.writerows(history)

    print(f"[Output] {output_csv}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Run a single CVRP algorithm trial.")
    p.add_argument("--algo",      required=True, choices=list(ALGO_JARS.keys()))
    p.add_argument("--instance",  required=True, type=Path)
    p.add_argument("--init-sol",  required=False, default=None, type=Path, dest="init_sol")
    p.add_argument("--output",    required=True, type=Path)
    p.add_argument("--time-limit",type=int,   default=DEFAULT_CONFIG["time_limit_sec"], dest="time_limit")
    p.add_argument("--d-max",     type=int,   default=DEFAULT_CONFIG["d_max"],   dest="d_max")
    p.add_argument("--d-min",     type=int,   default=DEFAULT_CONFIG["d_min"],   dest="d_min")
    p.add_argument("--gamma",     type=int,   default=DEFAULT_CONFIG["gamma"])
    p.add_argument("--varphi",    type=int,   default=DEFAULT_CONFIG["varphi"])
    p.add_argument("--eta-max",   type=float, default=DEFAULT_CONFIG["eta_max"], dest="eta_max")
    p.add_argument("--verbose",   action="store_true", default=False)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = {
        "time_limit_sec":  args.time_limit,
        "d_max":           args.d_max,
        "d_min":           args.d_min,
        "gamma":           args.gamma,
        "varphi":          args.varphi,
        "eta_max":         args.eta_max,
    }
    run_single(
        algo=args.algo,
        instance=Path(args.instance),
        init_sol=Path(args.init_sol) if args.init_sol is not None else None,
        output_csv=Path(args.output),
        cfg=cfg,
        verbose=args.verbose,
    )
