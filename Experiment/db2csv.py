"""
Convert all shared.db files under Experiment/remote_results/<instance_name>/ to CSV.

Structure assumed:
    remote_results/
        <instance_name>/
            <experiment_name>/
                shared.db

Output:
    results_ablation_csv/
        <instance_name>/
            <experiment_name>/
                global_best.csv
                solution_history.csv
                survivor_stats.csv
                improvement_stats.csv
"""

import argparse
import sqlite3
import csv
import os
from pathlib import Path

EXPERIMENT_PATH = Path(__file__).resolve().parent
SOURCE_ROOT = EXPERIMENT_PATH / "remote_results"
OUTPUT_ROOT = EXPERIMENT_PATH / "results_ablation_csv"

TABLES = ["global_best", "solution_history", "survivor_stats", "improvement_stats"]

# Columns to drop per table when writing CSV
SKIP_COLUMNS = {
    "global_best":       {"solution"},
    "solution_history":  {"solution"},
}


def export_db(db_path: Path, output_dir: Path, experiment_name: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        for table in TABLES:
            rows = conn.execute(f"SELECT * FROM {table}").fetchall()
            if not rows:
                print(f"  [{table}] empty, skipping")
                continue
            skip = SKIP_COLUMNS.get(table, set())
            cols = [c for c in rows[0].keys() if c not in skip]
            out_file = output_dir / f"{table}.csv"
            with open(out_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["experiment"] + cols)
                for row in rows:
                    writer.writerow([experiment_name] + [row[c] for c in cols])
            print(f"  -> {table}.csv  ({len(rows)} rows)")
        conn.close()
    except sqlite3.Error as e:
        print(f"  [SQLite error] {e}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("instance_name", nargs="?", default=None,
                        help="Instance name to convert. If omitted, converts all instances.")
    cli = parser.parse_args()

    if cli.instance_name:
        instance_dirs = [SOURCE_ROOT / cli.instance_name]
        if not instance_dirs[0].exists():
            print(f"Instance directory not found: {instance_dirs[0]}")
            return
    else:
        if not SOURCE_ROOT.exists():
            print(f"Source directory not found: {SOURCE_ROOT}")
            return
        instance_dirs = sorted(
            d for d in SOURCE_ROOT.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    total = 0
    for inst_dir in instance_dirs:
        experiments = sorted(
            d for d in inst_dir.iterdir()
            if d.is_dir() and (d / "shared.db").exists()
        )
        for exp_dir in experiments:
            total += 1

    if not total:
        print("No shared.db files found.")
        return

    print(f"Found {total} experiment(s). Writing to {OUTPUT_ROOT}\n")

    for inst_dir in instance_dirs:
        experiments = sorted(
            d for d in inst_dir.iterdir()
            if d.is_dir() and (d / "shared.db").exists()
        )
        for exp_dir in experiments:
            name = f"{inst_dir.name}/{exp_dir.name}"
            print(f"[{name}]")
            export_db(exp_dir / "shared.db", OUTPUT_ROOT / inst_dir.name / exp_dir.name, exp_dir.name)

    print("\nDone.")


if __name__ == "__main__":
    main()
