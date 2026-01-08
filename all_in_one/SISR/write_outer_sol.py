import vrplib
import sqlite3
import json
from pathlib import Path

instance_name = 'XLTEST-n1048-k139' # TODO

def save_best(db_path, running_time, score, solution, algo_name):
    try:
        sol_json = json.dumps(solution)
        print(sol_json)
    except TypeError as e:
        print(f"[Data Error] Solution serialization failed: {e}")
        return False

    try:
        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute("BEGIN IMMEDIATE")
            # conn.execute(
            #     "INSERT INTO solution_history (algo_name, score, solution, runningtime) VALUES (?, ?, ?, ?)",
            #     (algo_name, score, sol_json, running_time)
            # )

            # 4. 尝试更新全局最优 (Global Best)
            # 技巧：直接在 SQL 中判断 'score > ?'，避免先 SELECT 再 UPDATE 的两次交互
            # 假设 score 是越小越好 (Minimization)。如果是最大化问题，请改为 score < ?
            conn.execute(
                "UPDATE global_best SET score=?, solution=?, algo_name=?, runningtime=? WHERE id=1 AND score > ?",
                (score, sol_json, algo_name, running_time, score)
            )

            conn.commit()

    except sqlite3.OperationalError as e:
        # 常见错误：database is locked
        print(f"[DB Locked] {algo_name} failed to save: {e}")
        return False
    except Exception as e:
        print(f"[DB Error] {e}")
        return False

SISR_PATH = Path(__file__).resolve().parent

OUTER_PATH = SISR_PATH / 'outer_sol' / instance_name
DB_PATH = SISR_PATH / 'log_buffer' / instance_name / 'shared.db'

Sol_path = [item for item in OUTER_PATH.iterdir() if item.is_file()]

sol = vrplib.read_solution(Sol_path[0])


save_best(DB_PATH, -1e5, sol['cost'], sol['routes'], 'outer')
# save_best(DB_PATH, -1e5, 100, sol['routes'], 'outer')
