import os
import time
import sqlite3
import csv
import json
import shutil
import ast
from datetime import datetime
from pathlib import Path
from fabric import Connection

# ================= 配置区域 =================
# 服务器清单保持不变
SERVERS = [
    {"host": "10.90.91.100", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.101", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.124", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/CVRPLIB-2025-all-in-one/all_in_one/SISR/"},
    {"host": "10.90.91.125", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.126", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.127", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.163", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.167", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.49", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.51", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.231", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.232", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
]

FETCH_INTERVAL = 24 * 3600
LOCAL_ROOT = Path(__file__).resolve().parent
HISTORY_FILE = LOCAL_ROOT / "best_scores_history.json"


# ================= 工具函数 =================

def log_with_time(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def load_history():
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, indent=4, ensure_ascii=False)


# ================= 核心工作流 =================

def run_cycle():
    # 0. 统一本次运行的时间戳
    now = datetime.now()
    ts_folder = now.strftime("%Y%m%d_%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")

    # 1. 抓取 (Fetch) - 创建带时间戳的 DB 目录
    current_db_buffer = LOCAL_ROOT / "all_history_dbs" / ts_folder
    current_db_buffer.mkdir(parents=True, exist_ok=True)

    log_with_time(f"🚀 开始新周期: {ts_human}")

    for srv in SERVERS:
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                remote_log_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                result = conn.run(f"find {remote_log_root} -name 'shared.db'", hide=True, warn=True)
                if result.ok and result.stdout.strip():
                    for remote_file in result.stdout.strip().split('\n'):
                        # 提取 instance_name
                        instance_name = remote_file.split('/')[-2]
                        local_path = current_db_buffer / instance_name / "shared.db"
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        conn.get(remote_file, local=str(local_path))
            log_with_time(f"  [Fetch OK] {srv['host']}")
        except Exception as e:
            log_with_time(f"  [Fetch Error] {srv['host']}: {e}")

    # 2-4. 处理数据
    history = load_history()
    csv_root = LOCAL_ROOT / "all_history_csvs" / f"csv_{ts_folder}"
    sol_root = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    csv_root.mkdir(parents=True, exist_ok=True)
    sol_root.mkdir(parents=True, exist_ok=True)

    improvements = []

    for db_path in current_db_buffer.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # A. 转 CSV (每个库对应一个文件夹)
                inst_csv_dir = csv_root / instance_name
                inst_csv_dir.mkdir(parents=True, exist_ok=True)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                for table in [t[0] for t in cursor.fetchall()]:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    if rows:
                        with open(inst_csv_dir / f"{table}.csv", 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(rows[0].keys())
                            writer.writerows(rows)

                # B. 提取 SOL 并比分
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    old_best = history.get(instance_name)

                    if old_best is None or score < old_best:
                        status = "🆕 [New]" if old_best is None else "🔥 [Improved]"
                        diff = 0 if old_best is None else old_best - score
                        history[instance_name] = score
                        improvements.append(f"{status} {instance_name}: {score:.4f} (Diff: -{diff:.4f})")

                    # 生成 SOL
                    routes = ast.literal_eval(row['solution'])
                    with open(sol_root / f"{instance_name}.sol", 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except Exception as e:
            log_with_time(f"  [Process Error] {instance_name}: {e}")

    # 3. 归档处理
    # 将 CSV 打包
    if any(csv_root.iterdir()):
        shutil.make_archive(str(csv_root), 'zip', csv_root)
        shutil.rmtree(csv_root)  # 删除散文件，保留 .zip

    # 4. 战报
    save_history(history)
    report_path = LOCAL_ROOT / "all_history_reports" / f"report_{ts_folder}.txt"
    report_path.parent.mkdir(exist_ok=True)
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(f"SISR 自动周期总结 ({ts_human})\n" + "=" * 40 + "\n")
        f.write("\n".join(improvements) if improvements else "本次运行无分数更新。")

    log_with_time(f"✨ 周期结束。成绩单: {report_path.name}")


def main():
    log_with_time("🚀 [SISR 全历史记录系统] 已启动，24小时轮询一次...")
    while True:
        run_cycle()
        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()