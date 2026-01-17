import vrplib
import sqlite3
import json
from pathlib import Path


def save_best(db_path, running_time, score, solution, algo_name):
    """
    将解写入 SQLite 数据库。
    只有当 score 优于当前数据库中的 global_best 时才会更新。
    """
    try:
        sol_json = json.dumps(solution)
    except TypeError as e:
        print(f"[Data Error] Solution serialization failed: {e}")
        return False

    try:
        # 确保目录存在（防止数据库被删后无法重建目录的极端情况，虽然通常由外部保证）
        if not db_path.parent.exists():
            return False

        with sqlite3.connect(db_path, timeout=30.0) as conn:
            conn.execute("BEGIN IMMEDIATE")

            # 可选：如果你想记录所有历史解，取消下面注释
            # conn.execute(
            #     "INSERT INTO solution_history (algo_name, score, solution, runningtime) VALUES (?, ?, ?, ?)",
            #     (algo_name, score, sol_json, running_time)
            # )

            # 尝试更新全局最优 (Global Best)
            # score > ? 表示仅当新解(score) 小于(更优) 现有解时才更新
            # 注意：这里假设是最小化问题 (Minimization)
            conn.execute(
                "UPDATE global_best SET score=?, solution=?, algo_name=?, runningtime=? WHERE id=1 AND score > ?",
                (score, sol_json, algo_name, running_time, score)
            )

            # 获取受影响行数，判断是否发生了更新
            updated_rows = conn.total_changes
            conn.commit()

            return updated_rows > 0

    except sqlite3.OperationalError as e:
        # 常见错误：database is locked
        print(f"[DB Locked] {algo_name} failed to save to {db_path.name}: {e}")
        return False
    except Exception as e:
        print(f"[DB Error] {e}")
        return False

# 移除了原本的 if __name__ == '__main__': 块
# 这样避免被错误执行，确保它只作为模块被 import