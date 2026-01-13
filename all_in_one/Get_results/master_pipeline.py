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
# 1. 功能开关
SAVE_ALL_HISTORY = False  # True: 保存所有历史数据; False: DB和CSV只保留最新

# 2. 服务器清单 (共12台)
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

FETCH_INTERVAL = 24 * 3600  # 巡检间隔：24小时
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


def clean_old_data(dir_path):
    """清理目录逻辑：增加异常捕获以解决 Windows 文件占用锁定问题"""
    if dir_path.exists():
        try:
            shutil.rmtree(dir_path, ignore_errors=False)
            log_with_time(f"🧹 已清理旧目录: {dir_path.name}")
        except Exception as e:
            log_with_time(f"⚠️ 清理目录 {dir_path.name} 失败 (可能文件被占用): {e}")
    dir_path.mkdir(parents=True, exist_ok=True)


# ================= 核心工作流 =================

def run_cycle():
    now = datetime.now()
    ts_folder = now.strftime("%Y%m%d_%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")

    # 1. 路径初始化
    if SAVE_ALL_HISTORY:
        current_db_buffer = LOCAL_ROOT / "all_history_dbs" / ts_folder
        csv_save_path = LOCAL_ROOT / "all_history_csvs"
    else:
        current_db_buffer = LOCAL_ROOT / "log_buffer"
        csv_save_path = LOCAL_ROOT / "latest_csvs"
        # 仅在关闭历史记录模式下清理，防止空间溢出
        clean_old_data(current_db_buffer)
        clean_old_data(csv_save_path)

    current_db_buffer.mkdir(parents=True, exist_ok=True)
    csv_save_path.mkdir(parents=True, exist_ok=True)

    # 无论模式如何，SOL 和 Report 永远保留时间戳历史
    sol_history_dir = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    report_history_dir = LOCAL_ROOT / "all_history_reports"
    sol_history_dir.mkdir(parents=True, exist_ok=True)
    report_history_dir.mkdir(parents=True, exist_ok=True)

    log_with_time(f"🚀 周期开始: {ts_human} (历史记录模式: {'开启' if SAVE_ALL_HISTORY else '关闭'})")

    # 2. 抓取 (Fetch) 阶段
    for srv in SERVERS:
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                remote_log_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                # 远程查找所有 shared.db
                result = conn.run(f"find {remote_log_root} -name 'shared.db'", hide=True, warn=True)
                if result.ok and result.stdout.strip():
                    for remote_file in result.stdout.strip().split('\n'):
                        instance_name = remote_file.split('/')[-2]
                        local_path = current_db_buffer / instance_name / "shared.db"
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        conn.get(remote_file, local=str(local_path))
            log_with_time(f"  [Fetch OK] {srv['host']}")
        except Exception as e:
            log_with_time(f"  [Fetch Error] {srv['host']}: {e}")

    # --- 阶段转换提示 ---
    print("-" * 60)
    log_with_time("✅ 所有服务器采集完毕。开始整理本地 CSV 并对比历史分数...")
    print("-" * 60)

    # 3. 处理数据 (CSV & SOL & Report) 阶段
    history = load_history()
    improvements = []
    temp_csv_root = csv_save_path / f"csv_{ts_folder}"
    temp_csv_root.mkdir(parents=True, exist_ok=True)

    # 遍历下载好的所有 shared.db
    for db_path in current_db_buffer.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            # 使用 with 显式管理连接，确保处理完即刻关闭连接，避免 Windows 文件占用
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # A. 转换所有表为 CSV
                inst_csv_dir = temp_csv_root / instance_name
                inst_csv_dir.mkdir(parents=True, exist_ok=True)
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = [t[0] for t in cursor.fetchall()]

                for table in tables:
                    cursor.execute(f"SELECT * FROM {table}")
                    rows = cursor.fetchall()
                    if rows:
                        csv_file = inst_csv_dir / f"{table}.csv"
                        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            writer.writerow(rows[0].keys())
                            writer.writerows(rows)

                # B. 提取最佳解并对比分数
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    old_best = history.get(instance_name)

                    # 发现更好的成绩
                    if old_best is None or score < old_best:
                        status = "🆕 [New]" if old_best is None else "🔥 [Improved]"
                        diff = 0 if old_best is None else old_best - score
                        history[instance_name] = score
                        improvements.append(f"{status} {instance_name}: {score:.4f} (Diff: -{diff:.4f})")

                    # 解析并保存标准的 .sol 文件
                    routes = ast.literal_eval(row['solution'])
                    sol_file = sol_history_dir / f"{instance_name}.sol"
                    with open(sol_file, 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except Exception as e:
            log_with_time(f"  [Process Error] {instance_name}: {e}")

    # 4. 打包并清理临时 CSV 文件夹
    if any(temp_csv_root.iterdir()):
        shutil.make_archive(str(temp_csv_root), 'zip', temp_csv_root)
        try:
            shutil.rmtree(temp_csv_root)
        except:
            pass

    # 5. 保存历史记录及生成战报
    save_history(history)
    report_file = report_history_dir / f"report_{ts_folder}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        header = f"SISR 自动化分析报告 ({ts_human})\n"
        f.write(header + "=" * 40 + "\n")
        f.write("\n".join(improvements) if improvements else "本次巡检无分数更新。")

    log_with_time(f"✨ 周期任务完成。报告已生成: {report_file.name}")


# ================= 主入口 =================

def main():
    log_with_time("🚀 系统启动。正在进入 24 小时巡检模式...")
    while True:
        try:
            run_cycle()
            log_with_time(f"💤 任务休眠中。下次运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} 之后约 24 小时。")
            time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            log_with_time("👋 用户停止脚本运行。")
            break
        except Exception as e:
            log_with_time(f"❌ 主程序捕获严重异常: {e}")
            log_with_time("将在 60 秒后重试...")
            time.sleep(60)


if __name__ == "__main__":
    main()