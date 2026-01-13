import os
import time
import sqlite3
import csv
import json
import shutil
import ast
import traceback
from datetime import datetime
from pathlib import Path
from fabric import Connection

# ================= 配置区域 =================
# 1. 服务器配置
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

# 2. 运行参数
FETCH_INTERVAL = 24 * 3600  # 24小时 (秒)
LOCAL_ROOT = Path(__file__).resolve().parent
LOG_BUFFER = LOCAL_ROOT / "log_buffer"


# ================= 核心功能模块 =================

def log_with_time(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def step1_fetch_data():
    log_with_time("开始执行 Step 1: 抓取远程数据库...")
    for srv in SERVERS:
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                remote_log_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                result = conn.run(f"find {remote_log_root} -name 'shared.db'", hide=True, warn=True)

                if not result.ok or not result.stdout.strip():
                    continue

                for remote_file in result.stdout.strip().split('\n'):
                    rel_path = os.path.relpath(remote_file, srv['base_path'])
                    local_path = LOCAL_ROOT / rel_path
                    local_path.parent.mkdir(parents=True, exist_ok=True)
                    conn.get(remote_file, local=str(local_path))
            log_with_time(f"  Successfully fetched from {srv['host']}")
        except Exception as e:
            log_with_time(f"  Error fetching from {srv['host']}: {e}")


def step2_convert_to_csv():
    log_with_time("开始执行 Step 2: 转换数据库到 CSV...")
    if not LOG_BUFFER.exists(): return

    timestamp = datetime.now().strftime("%Y%m%d%H%M")
    csv_root = LOCAL_ROOT / f"log_csv_{timestamp}"

    has_data = False
    for db_path in LOG_BUFFER.rglob("shared.db"):
        instance_name = db_path.parent.name
        target_dir = csv_root / instance_name
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                for table in cursor.fetchall():
                    table_name = table[0]
                    cursor.execute(f"SELECT * FROM {table_name}")
                    rows = cursor.fetchall()
                    cols = [d[0] for d in cursor.description]
                    with open(target_dir / f"{table_name}.csv", 'w', newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        writer.writerow(cols)
                        writer.writerows(rows)
            has_data = True
        except Exception as e:
            log_with_time(f"  Error converting {db_path}: {e}")

    if has_data:
        shutil.make_archive(str(csv_root), 'zip', csv_root)
        log_with_time(f"  CSV 转换完成并已打包: {csv_root}.zip")


def step3_extract_sol():
    log_with_time("开始执行 Step 3: 提取最优解 .sol 文件...")
    if not LOG_BUFFER.exists(): return

    sol_root = LOCAL_ROOT / "output_sol" / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    sol_root.mkdir(parents=True, exist_ok=True)

    for db_path in LOG_BUFFER.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row[0]:
                    routes = ast.literal_eval(row[0])
                    score = row[1]
                    with open(sol_root / f"{instance_name}.sol", 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except Exception as e:
            log_with_time(f"  Error extracting sol from {instance_name}: {e}")
    log_with_time(f"  .sol 文件提取完成，存放在: {sol_root}")


# ================= 主循环 =================

def main():
    log_with_time("🚀 自动化流水线已启动...")
    while True:
        cycle_start = time.time()

        # 执行所有任务
        step1_fetch_data()
        step2_convert_to_csv()
        step3_extract_sol()

        log_with_time("✨ 本次循环所有任务已完成。")
        log_with_time(f"💤 正在休眠，将在 24 小时后再次运行...")

        # 等待 24 小时
        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()