"""
test_one_run.py — Run a single (algo, instance, initial_solution) trial using file-version JARs.

The file-version JARs write results directly to disk:
  - CSV:  <output_dir>/<instance>.csv   (semicolon-separated, no header: time;score, improvements only)
  - Sol:  <output_dir>/<instance>.sol   (CVRPLib format, overwritten on each improvement)

Usage:
    python test_one_run.py \
        --algo AILS2 \
        --instance Instances/XL-n1048-k237.vrp \
        --output-dir results/AILS2 \
        [--init-sol Initial_sols/XL-n1048-k237.sol] \
        [--time-limit 3600]
"""

import argparse
import csv
import subprocess
import sys
import threading
from pathlib import Path

import psutil

# ─── Paths ────────────────────────────────────────────────────────────────────

EXPERIMENT_DIR = Path(__file__).resolve().parent
ROOT_DIR = EXPERIMENT_DIR.parent
SRC_DIR = ROOT_DIR / "src"

ALGO_JARS = {
    "AILS2":               SRC_DIR / "AILS-II_origin"     / "AILSII.jar",
    "AILS2_ws":            SRC_DIR / "AILS-II_continue"   / "AILSII.jar",
    "AILS2_Eoh_Acc":       SRC_DIR / "AILS2_EoH_Acc"      / "AILSII.jar",
    "AILS2_Eoh_Acc_large": SRC_DIR / "AILS2_EoH_Acc_large" / "AILSII.jar",
    "AILS2_Eoh_Omega2":    SRC_DIR / "AILS2_EoH_Omega2"   / "AILSII.jar",
    "AILS2_Eoh_Ruin":      SRC_DIR / "AILS2_EoH_Ruin"     / "AILSII.jar",
    "AILS2_Eoh_Ruin2":     SRC_DIR / "AILS2_EoH_Ruin2"    / "AILSII.jar",
}

DEFAULT_CONFIG = {
    "time_limit_sec": 3600,
    "d_max": 30,
    "d_min": 15,
    "gamma": 30,
    "varphi": 40,
    "eta_max": 1.0,
}

# ─── Process helpers ──────────────────────────────────────────────────────────

def kill_tree(pid: int) -> None:
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


def build_cmd(jar: Path, instance: Path, output_dir: Path, cfg: dict,
              init_sol: Path | None = None) -> list[str]:
    cmd = [
        "java", "-jar", str(jar),
        "-file",              str(instance.resolve()),
        "-rounded",           "true",
        "-best",              "0",
        "-limit",             str(cfg["time_limit_sec"]),
        "-stoppingCriterion", "Time",
        "-dMax",              str(cfg["d_max"]),
        "-dMin",              str(cfg["d_min"]),
        "-gamma",             str(cfg["gamma"]),
        "-varphi",            str(cfg["varphi"]),
        "-etaMax",            str(cfg["eta_max"]),
        "-output",            str(output_dir.resolve()),
    ]
    if init_sol is not None:
        cmd += ["-resume", str(init_sol.resolve())]
    return cmd


def read_csv(csv_path: Path) -> list[tuple[float, float]]:
    """Read semicolon-separated time;score CSV written by the Java file-version."""
    rows = []
    if not csv_path.exists():
        return rows
    with open(csv_path, newline="") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split(";")
            if len(parts) >= 2:
                try:
                    rows.append((float(parts[0]), float(parts[1])))
                except ValueError:
                    pass
    return rows


# ─── Trial runner ─────────────────────────────────────────────────────────────

def run_single(algo: str, instance: Path, init_sol: Path | None,
               output_dir: Path, cfg: dict, verbose: bool = False) -> None:
    """
    Run one (algo, instance, init_sol) trial.

    The Java process writes <instance_stem>.csv and <instance_stem>.sol into output_dir.
    After the run, re-writes the CSV as comma-separated with header [timestamp_sec, score].

    init_sol: path to a .sol file for warm start; None means construct from scratch.
    """
    jar = ALGO_JARS[algo]
    if not jar.exists():
        print(f"[Error] JAR not found: {jar}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    instance_stem = instance.stem

    print(f"[Setup] instance={instance.name}  algo={algo}  "
          f"init_sol={init_sol.name if init_sol else 'None'}")

    cmd = build_cmd(jar, instance, output_dir, cfg, init_sol)
    print(f"[Run]   {' '.join(cmd)}")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            text=True, bufsize=1)

    def drain(stream, do_print):
        if stream:
            for line in stream:
                if do_print:
                    print(line, end="", flush=True)

    t = threading.Thread(target=drain, args=(proc.stdout, verbose), daemon=True)
    t.start()

    try:
        proc.wait(timeout=cfg["time_limit_sec"] + 30)
    except subprocess.TimeoutExpired:
        print(f"[Timeout] killing {algo}")
        kill_tree(proc.pid)
        proc.wait()

    t.join(timeout=5)

    stderr_out = proc.stderr.read() if proc.stderr else ""
    if stderr_out:
        print(f"[stderr]\n{stderr_out}", file=sys.stderr)

    # Re-write the semicolon CSV as comma-separated with header.
    raw_csv = output_dir / f"{instance_stem}.csv"
    rows = read_csv(raw_csv)
    print(f"[Done]  {len(rows)} improvement records in {raw_csv}")

    with open(raw_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_sec", "score"])
        writer.writerows(rows)


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    p = argparse.ArgumentParser(description="Run a single CVRP file-version trial.")
    p.add_argument("--algo",       required=True, choices=list(ALGO_JARS.keys()))
    p.add_argument("--instance",   required=True, type=Path)
    p.add_argument("--output-dir", required=True, type=Path, dest="output_dir")
    p.add_argument("--init-sol",   required=False, default=None, type=Path, dest="init_sol")
    p.add_argument("--time-limit", type=int,   default=DEFAULT_CONFIG["time_limit_sec"], dest="time_limit")
    p.add_argument("--d-max",      type=int,   default=DEFAULT_CONFIG["d_max"],          dest="d_max")
    p.add_argument("--d-min",      type=int,   default=DEFAULT_CONFIG["d_min"],          dest="d_min")
    p.add_argument("--gamma",      type=int,   default=DEFAULT_CONFIG["gamma"])
    p.add_argument("--varphi",     type=int,   default=DEFAULT_CONFIG["varphi"])
    p.add_argument("--eta-max",    type=float, default=DEFAULT_CONFIG["eta_max"],        dest="eta_max")
    p.add_argument("--verbose",    action="store_true", default=False)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    cfg = {
        "time_limit_sec": args.time_limit,
        "d_max":          args.d_max,
        "d_min":          args.d_min,
        "gamma":          args.gamma,
        "varphi":         args.varphi,
        "eta_max":        args.eta_max,
    }
    run_single(
        algo=args.algo,
        instance=args.instance,
        init_sol=args.init_sol,
        output_dir=args.output_dir,
        cfg=cfg,
        verbose=args.verbose,
    )
