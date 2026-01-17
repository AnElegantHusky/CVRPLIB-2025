import sys
import sqlite3
import json
import time
import os


def safe_inject(db_path, algo_name, score, solution_json):
    """
    Safely injects a solution into the SQLite database.
    Uses WAL mode and retries to prevent locking issues with the main process.
    """
    if not os.path.exists(db_path):
        return False, "DB file not found"

    max_retries = 5

    for i in range(max_retries):
        conn = None
        try:
            # Connect with a long timeout
            conn = sqlite3.connect(db_path, timeout=60.0)

            # 1. Enable WAL mode to allow concurrent reading/writing
            conn.execute("PRAGMA journal_mode=WAL;")

            # 2. Start transaction immediately to acquire write lock
            conn.execute("BEGIN IMMEDIATE")

            # 3. Update Global Best ONLY if the new score is better
            # Note: Assuming minimization problem (score > new_score)
            cursor = conn.execute(
                "UPDATE global_best SET score=?, solution=?, algo_name=?, runningtime=? WHERE id=1 AND score > ?",
                (score, solution_json, algo_name, time.time(), score)
            )

            updated_rows = cursor.rowcount
            conn.commit()

            if updated_rows > 0:
                return True, "Updated BKS (Global Best)"
            else:
                return True, "Score not better than existing BKS, skipped"

        except sqlite3.OperationalError as e:
            if "locked" in str(e):
                time.sleep(1 + i)  # Linear backoff sleep
                continue
            return False, f"Operational Error: {str(e)}"
        except Exception as e:
            return False, f"General Error: {str(e)}"
        finally:
            if conn:
                conn.close()

    return False, "Database locked after max retries"


if __name__ == "__main__":
    # Arguments: <db_path> <score> <solution_json_string>
    if len(sys.argv) < 4:
        print("Usage: python server_db_injector.py <db_path> <score> <sol_json>")
        sys.exit(1)

    db_path = sys.argv[1]
    try:
        score = float(sys.argv[2])
    except ValueError:
        print("FAILURE: Invalid score format")
        sys.exit(1)

    sol_json = sys.argv[3]

    # Execute injection
    success, msg = safe_inject(db_path, "External_Inject", score, sol_json)

    # Print status to stdout for the local pipeline to capture
    prefix = "SUCCESS" if success else "FAILURE"
    print(f"{prefix}: {msg}")