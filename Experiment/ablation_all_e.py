import os
import subprocess
import sys
import numpy as np
import time
import multiprocessing
import traceback
import gc
import vrplib
import sqlite3
import psutil
import json
import argparse
from pathlib import Path


# ================= Path Constants =================

EXPERIMENT_PATH = Path(__file__).resolve().parent
ROOT_PATH = EXPERIMENT_PATH.parent

MINUTE_SEC_DEFAULT = 30
DAY = 20

EXPERIMENT_NAME = Path(__file__).stem


def make_config(one_day_sec):
    # ================= Config =================
    # Edit this section to configure the experiment.
    # CLI args (instance_name, running_time_min, warmup_sec, update_interval_sec) override these defaults.
    return {
        # --- Run-level settings ---
        "instances_path": "Instances",   # relative to Experiment/
        "instance_name": "XL-n1234-k55",              # overridden by CLI; required
        "initial_solution": None,
        # "initial_solution": EXPERIMENT_PATH / "solution_history_first.sol",  # path to a .sol file; None means no warm-start seed
        "running_time_min": DAY * one_day_sec / 60,        # total wall-clock budget (minutes)
        "warmup_sec": one_day_sec // 3,        # initial free-run before monitoring starts
        "update_interval_sec": one_day_sec // 3,  # how often the monitor polls the DB
        "writing_interval_sec": 60,         # how often algorithms write to the DB

        # --- Shared AILS parameters ---
        "shared_params": {
            "dMax": 30,
            "dMin": 15,
            "gamma": 30,
            "varphi": 40,
        },

        # --- Tier 1: Exploration ---
        # Never terminated by the main process. Run once until their own time limit.
        "tier1": [
            {"name": "G_AILS2_10d", "type": "ails", "jar": ROOT_PATH / "AILS2" / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
             "extra_args": ["-etaMax", "1", "-limit", str(one_day_sec * 10)]},
            {"name": "G_AILS2_1d",  "type": "ails",
             "jar": ROOT_PATH / "AILS2" / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
             "extra_args": ["-etaMax", "0.01", "-limit", str(one_day_sec)]},
            {"name": "G_HGS",  "type": "hgs",
             "exe": ROOT_PATH / "HGS-TV" / "build" / ("hgs.exe" if os.name == "nt" else "hgs")},
            {"name": "G_AILS2_5d", "type": "ails", "jar": ROOT_PATH / "AILS2" / "target" / "AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar",
             "extra_args": ["-etaMax", "0.01", "-limit", str(one_day_sec * 5)]},
            ],

        # --- Tier 2: Warm-start ---
        # Never killed by the main process. Restarted automatically when they finish.
        "tier2": [],

        # --- Tier 3: Exploitation ---
        # Killed and restarted whenever a new global best is found.
        # For Java algorithms set "type": "ails". For C++ set "type": "filo" or "hgs".
        "tier3": [],
    }


# ================= Shared DB =================

class SharedDB:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):
        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                if os.path.exists(self.db_path + "-wal"): os.remove(self.db_path + "-wal")
                if os.path.exists(self.db_path + "-shm"): os.remove(self.db_path + "-shm")
            except OSError as e:
                print(f"[DB Init Warning] Failed to delete old DB: {e}")

        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout = 30000;")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS global_best (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    score REAL,
                    solution TEXT,
                    algo_name TEXT,
                    runningtime REAL
                );
            """)
            conn.execute(
                "INSERT OR IGNORE INTO global_best (id, score, solution, algo_name, runningtime) VALUES (1, 1e20, '', '', 0)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS solution_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    algo_name TEXT,
                    score REAL,
                    solution TEXT,
                    runningtime REAL
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_algo_time ON solution_history (algo_name, runningtime);")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS survivor_stats (
                    algo_name TEXT PRIMARY KEY,
                    seed_count INTEGER DEFAULT 0
                );
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS improvement_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    seed_algo TEXT,
                    seed_score REAL,
                    winner_algo TEXT,
                    winner_score REAL,
                    improvement REAL,
                    recording_time REAL
                );
            """)
            conn.commit()

    def get_status(self):
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT score, algo_name, runningtime, solution FROM global_best WHERE id=1"
            ).fetchone()
            return dict(row) if row else None

    def log_survivor(self, algo_name):
        if not algo_name:
            return
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO survivor_stats (algo_name, seed_count)
                VALUES (?, 1)
                ON CONFLICT(algo_name) DO UPDATE SET seed_count = seed_count + 1
            """, (algo_name,))
            conn.commit()

    def load_initial_solution(self, score, routes, algo_name="initial"):
        """Write a known solution into global_best before algorithms start.

        Uses BEGIN IMMEDIATE + conditional WHERE so the row is only updated if
        the given score is better than what's already there — same pattern as
        write_outer_sol.save_best() and SQLiteHelper.saveBest() in Java, which
        is the correct approach for a table written by concurrent processes.
        """
        sol_json = json.dumps(routes)
        with sqlite3.connect(self.db_path, timeout=30.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                "UPDATE global_best SET score=?, solution=?, algo_name=?, runningtime=? WHERE id=1 AND score > ?",
                (score, sol_json, algo_name, 0.0, score),
            )
            conn.commit()

    def log_improvement(self, seed_algo, seed_score, winner_algo, winner_score, recording_time):
        improvement = 0.0 if seed_score > 1e19 else seed_score - winner_score
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO improvement_stats
                    (seed_algo, seed_score, winner_algo, winner_score, improvement, recording_time)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (seed_algo, seed_score, winner_algo, winner_score, improvement, recording_time))
            conn.commit()


# ================= Helpers =================

def smart_decode(byte_data):
    if not byte_data:
        return ""
    try:
        return byte_data.decode("utf-8")
    except Exception:
        return byte_data.decode("latin-1", errors="replace")


def kill_process_tree(pid):
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=1)
        for p in alive:
            p.kill()
        parent.terminate()
        parent.wait(1)
    except psutil.NoSuchProcess:
        pass


def run_external_process(cmd):
    print(" ".join(str(c) for c in cmd))
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        if stderr:
            print(f"[Error] {cmd[0]}: {smart_decode(stderr)}")
    except Exception as e:
        print(f"[Exception] Failed to run {cmd[0]}: {e}")


def build_ails_cmd(jar, instance_path, shared_db_path, start_time, shared_params, writing_interval, extra_args):
    cmd = [
        "java", "-jar", str(jar),
        "-file", str(instance_path),
        "-sharedDB", str(shared_db_path),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None",
        "-crtRunningTime", str(time.time() - start_time),
        "-stoppingCriterion", "Time",
        "-dMax", str(shared_params["dMax"]),
        "-dMin", str(shared_params["dMin"]),
        "-gamma", str(shared_params["gamma"]),
        "-varphi", str(shared_params["varphi"]),
        "-startTime", str(start_time),
        "-updateInterval", str(writing_interval),
    ]
    cmd.extend(str(a) for a in extra_args)
    return cmd


def build_filo_cmd(exe, instance_path, shared_db_path, start_time, max_running_sec, writing_interval):
    return [
        str(exe),
        str(instance_path),
        "--shared-db", str(shared_db_path),
        "--start-time", str(start_time),
        "--max-running-seconds", str(max_running_sec),
        "--update-interval-seconds", str(writing_interval),
    ]


def build_hgs_cmd(exe, instance_path, shared_db_path, start_time, max_running_sec, writing_interval):
    return [
        str(exe),
        str(instance_path),
        "-sharedDB", str(shared_db_path),
        "-startTime", str(start_time),
        "-t", str(max_running_sec),
        "-type", "Uchoa",
        "-updateInterval", str(writing_interval),
    ]


# ================= Process Manager =================

class ProcessManager:
    """
    Manages three tiers of algorithm processes:
      Tier 1 (exploration)  — started once, never killed, removed from tracking when finished.
      Tier 2 (warm-start)   — never killed, automatically restarted when they finish.
      Tier 3 (exploitation) — killed and restarted whenever a new global best is found.

    The current global-best holder is always treated as a survivor regardless of tier.
    """

    def __init__(self, tier1_configs, tier2_configs, tier3_configs):
        self.tier1_configs = tier1_configs
        self.tier2_configs = tier2_configs
        self.tier3_configs = tier3_configs
        self.process_dict: dict[str, multiprocessing.Process] = {}
        self.finished: set[str] = set()   # tier1 processes that have completed

        self._tier1_names = {c["name"] for c in tier1_configs}
        self._tier2_names = {c["name"] for c in tier2_configs}

    # --- Public interface ---

    def start_all(self, cmd_map: dict):
        """Launch every algorithm for the first time."""
        for configs in (self.tier1_configs, self.tier2_configs, self.tier3_configs):
            for cfg in configs:
                self._start(cfg["name"], cmd_map[cfg["name"]])

    def tick(self, cmd_map: dict, current_best_name: str | None):
        """
        Called by the monitor loop on every event (new best or need_restart).
        Handles tier1 cleanup, tier3 kill+restart, and tier2 restart-if-dead.
        """
        survivor_names = self._tier1_names | self._tier2_names | self.finished
        if current_best_name:
            survivor_names.add(current_best_name)

        # Retire finished tier1 processes
        for name in list(self._tier1_names - self.finished):
            p = self.process_dict.get(name)
            if p and not p.is_alive():
                p.join(timeout=1)
                del self.process_dict[name]
                self.finished.add(name)

        # Kill non-survivors (tier3 and any tier2 that lost survivor status — shouldn't happen)
        for name, p in list(self.process_dict.items()):
            if name not in survivor_names and p and p.is_alive():
                kill_process_tree(p.pid)
                p.join(timeout=1)
                del self.process_dict[name]

        gc.collect()

        # Restart any dead process (tier2 warm-start + tier3 exploitation)
        for configs in (self.tier2_configs, self.tier3_configs):
            for cfg in configs:
                name = cfg["name"]
                if name not in self.finished:
                    self._restart_if_dead(name, cmd_map[name])

    def needs_restart(self) -> bool:
        """True if any tier2 process has died and needs restarting."""
        for cfg in self.tier2_configs:
            name = cfg["name"]
            p = self.process_dict.get(name)
            if p and not p.is_alive():
                return True
        return False

    def cleanup(self):
        for p in self.process_dict.values():
            if p and p.is_alive():
                kill_process_tree(p.pid)
                p.join()
        gc.collect()

    # --- Private helpers ---

    def _start(self, name: str, cmd: list):
        p = multiprocessing.Process(target=run_external_process, args=(cmd,), name=name)
        p.start()
        self.process_dict[name] = p

    def _restart_if_dead(self, name: str, cmd: list):
        p = self.process_dict.get(name)
        if not p or not p.is_alive():
            self._start(name, cmd)


# ================= Main =================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instances_path", nargs="?", default="Instances",
                        help="Folder of all instances (relative to Experiment/).")
    parser.add_argument("instance_name", nargs="?", default="XL-n1234-k55",
                        help="Instance name (without .vrp extension).")
    parser.add_argument("--minute_sec", type=int, default=MINUTE_SEC_DEFAULT,
                        help="Seconds per 'day' unit (default: 30*60=1800).")
    parser.add_argument("--initial_solution", default=None)
    parser.add_argument("--running_time_min", type=int, default=None)
    parser.add_argument("--warmup_sec",        type=int, default=None)
    parser.add_argument("--update_interval_sec", type=int, default=None)
    cli = parser.parse_args()

    one_day_sec = cli.minute_sec * 60
    CONFIG = make_config(one_day_sec)
    if cli.initial_solution is not None:
        CONFIG["initial_solution"] = cli.initial_solution
    if cli.running_time_min is not None:
        CONFIG["running_time_min"] = cli.running_time_min
    if cli.warmup_sec is not None:
        CONFIG["warmup_sec"] = cli.warmup_sec
    if cli.update_interval_sec is not None:
        CONFIG["update_interval_sec"] = cli.update_interval_sec

    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass

    # --- Resolve paths ---
    instance_path = EXPERIMENT_PATH / cli.instances_path / f"{cli.instance_name}.vrp"
    log_path = EXPERIMENT_PATH / "remote_results" / cli.instance_name / EXPERIMENT_NAME
    log_path.mkdir(parents=True, exist_ok=True)
    shared_db_path = log_path / "shared.db"

    # --- Load instance ---
    vrp_data = vrplib.read_instance(str(instance_path))

    # --- Init DB ---
    db = SharedDB(shared_db_path)
    db.init_db()

    if cli.initial_solution:
        sol = vrplib.read_solution(str(cli.initial_solution))
        db.load_initial_solution(sol["cost"], sol["routes"])
        print(f"[Init] Seeded global_best from {cli.initial_solution} (cost={sol['cost']})")

    start_time = time.time()
    max_running_sec = CONFIG["running_time_min"] * 60
    shared_params = CONFIG["shared_params"]
    writing_interval = CONFIG["writing_interval_sec"]

    # --- Build command map ---
    # Each algorithm name maps to its fully-built command list.
    cmd_map: dict[str, list] = {}

    def build_cmd(cfg):
        t = cfg["type"]
        if t == "ails":
            return build_ails_cmd(cfg["jar"], instance_path, shared_db_path,
                                  start_time, shared_params, writing_interval, cfg["extra_args"])
        elif t == "filo":
            return build_filo_cmd(cfg["exe"], instance_path, shared_db_path,
                                  start_time, max_running_sec, writing_interval)
        elif t == "hgs":
            return build_hgs_cmd(cfg["exe"], instance_path, shared_db_path,
                                 start_time, max_running_sec, writing_interval)
        else:
            raise ValueError(f"Unknown algorithm type: {t!r}")

    for tier in ("tier1", "tier2", "tier3"):
        for cfg in CONFIG[tier]:
            cmd_map[cfg["name"]] = build_cmd(cfg)

    # --- Start processes ---
    manager = ProcessManager(CONFIG["tier1"], CONFIG["tier2"], CONFIG["tier3"])
    manager.start_all(cmd_map)

    time.sleep(CONFIG["warmup_sec"])

    # --- Monitor loop ---
    crt_best = {"algo_name": None, "score": float("inf")}

    try:
        while time.time() - start_time < max_running_sec:
            try:
                global_best = db.get_status()
                has_new_best = global_best and crt_best["score"] > global_best["score"]
                need_restart = manager.needs_restart()

                if has_new_best:
                    print(global_best["algo_name"], global_best["score"])
                    db.log_survivor(global_best["algo_name"])
                    if crt_best["algo_name"] is not None:
                        db.log_improvement(
                            crt_best["algo_name"], crt_best["score"],
                            global_best["algo_name"], global_best["score"],
                            time.time() - start_time,
                        )
                    crt_best["score"] = global_best["score"]
                    crt_best["algo_name"] = global_best["algo_name"]

                if has_new_best or need_restart:
                    if global_best and not has_new_best:
                        crt_best["score"] = global_best["score"]
                        crt_best["algo_name"] = global_best["algo_name"]
                    manager.tick(cmd_map, crt_best["algo_name"])

            except Exception:
                exc_type, exc_value, _ = sys.exc_info()
                print(
                    f"\n[Monitor Error] {exc_type.__name__}: {exc_value}\n"
                    f"crt_best={crt_best}\n"
                    f"{traceback.format_exc()}"
                )

            time.sleep(CONFIG["update_interval_sec"])

    except KeyboardInterrupt:
        print("Stopping...")
    except Exception:
        traceback.print_exc()
    finally:
        manager.cleanup()
        print("Done.")


if __name__ == "__main__":
    main()
