import os
import time
import sqlite3
import csv
import json
import shutil
import ast
import requests
from datetime import datetime
from pathlib import Path
from fabric import Connection
from bs4 import BeautifulSoup

# ================= 配置区域 =================
# 1. 功能开关
SAVE_ALL_HISTORY = False  # True: 保存所有历史数据库; False: 仅保留最新下载的DB
EXPORT_CSV = False  # 【新增】True: 提取并压缩CSV; False: 跳过CSV生成（极大提升速度）

# 2. 服务器清单
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


def clean_old_data(dir_path):
    if dir_path.exists():
        try:
            shutil.rmtree(dir_path, ignore_errors=False)
            log_with_time(f"🧹 已清理旧目录: {dir_path.name}")
        except Exception as e:
            log_with_time(f"⚠️ 清理目录 {dir_path.name} 失败: {e}")
    dir_path.mkdir(parents=True, exist_ok=True)


# ================= 爬虫工具函数 =================

def get_cvrplib_instances_float():
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"
    headers = {"User-Agent": "Mozilla/5.0"}
    log_with_time("🌍 正在连接 CVRPLIB 获取最新纪录(BKS)...")
    try:
        response = requests.get(target_url, headers=headers, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('main section table') or soup.find('table')
        if not table: return {}
        data_dict = {}
        tbody = table.find('tbody')
        if tbody:
            for row in tbody.find_all('tr'):
                cols = row.find_all('td')
                if len(cols) >= 3:
                    key = cols[0].get_text(strip=True)
                    raw_val = cols[2].get_text(strip=True)
                    try:
                        clean_val = raw_val.replace('$', '').replace(',', '').replace('{', '').replace('}', '')
                        data_dict[key] = float(clean_val)
                    except ValueError:
                        continue
        log_with_time(f"✅ 获取榜单成功，共 {len(data_dict)} 条记录。")
        return data_dict
    except Exception as e:
        log_with_time(f"⚠️ 获取榜单失败: {e}")
        return {}


# ================= 核心工作流 =================

def run_cycle():
    now = datetime.now()
    ts_folder = now.strftime("%Y%m%d_%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")

    leaderboard_data = get_cvrplib_instances_float()

    # 1. 路径初始化
    if SAVE_ALL_HISTORY:
        current_db_buffer = LOCAL_ROOT / "all_history_dbs" / ts_folder
        csv_save_path = LOCAL_ROOT / "all_history_csvs"
    else:
        current_db_buffer = LOCAL_ROOT / "log_buffer"
        csv_save_path = LOCAL_ROOT / "latest_csvs"
        clean_old_data(current_db_buffer)
        clean_old_data(csv_save_path)

    current_db_buffer.mkdir(parents=True, exist_ok=True)
    csv_save_path.mkdir(parents=True, exist_ok=True)
    sol_history_dir = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    report_history_dir = LOCAL_ROOT / "all_history_reports"
    sol_history_dir.mkdir(parents=True, exist_ok=True)
    report_history_dir.mkdir(parents=True, exist_ok=True)

    log_with_time(
        f"🚀 周期开始: {ts_human} (模式: DB存储={'历史' if SAVE_ALL_HISTORY else '最新'}, CSV导出={'开启' if EXPORT_CSV else '关闭'})")

    # 2. 抓取阶段
    for srv in SERVERS:
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                remote_log_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
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

    print("-" * 60)
    log_with_time("✅ 采集完毕。开始分析数据...")
    print("-" * 60)

    # 3. 处理数据 & 对比
    local_history = load_history()
    bks_breakers = []
    local_only_improvements = []

    # 仅在需要时准备CSV临时目录
    temp_csv_root = csv_save_path / f"csv_{ts_folder}" if EXPORT_CSV else None
    if temp_csv_root: temp_csv_root.mkdir(parents=True, exist_ok=True)

    for db_path in current_db_buffer.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # --- A. 按需转换 CSV (速度瓶颈点) ---
                if EXPORT_CSV and temp_csv_root:
                    inst_csv_dir = temp_csv_root / instance_name
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

                # --- B. 提取最佳解并对比 ---
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    old_local_best = local_history.get(instance_name)
                    bks_val = leaderboard_data.get(instance_name)

                    if old_local_best is None or score < old_local_best:
                        local_history[instance_name] = score
                        local_diff = 0 if old_local_best is None else old_local_best - score

                        if bks_val is not None and score < bks_val:
                            gap = bks_val - score
                            msg = f"🏆 [NEW RECORD] {instance_name} | Our: {score:.4f} < BKS: {bks_val:.4f} (Gap: -{gap:.4f})"
                            bks_breakers.append(msg)
                            log_with_time(msg)
                        else:
                            msg = f"📈 [Self Improved] {instance_name} | Now: {score:.4f} (Improved: -{local_diff:.4f})"
                            if bks_val: msg += f" | Gap to BKS: +{score - bks_val:.4f}"
                            local_only_improvements.append(msg)
                            log_with_time(msg)

                    # 保存 .sol 文件
                    routes = ast.literal_eval(row['solution'])
                    with open(sol_history_dir / f"{instance_name}.sol", 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")

        except Exception as e:
            log_with_time(f"  [Process Error] {instance_name}: {e}")

    # 4. 打包清理 CSV
    if EXPORT_CSV and temp_csv_root and any(temp_csv_root.iterdir()):
        shutil.make_archive(str(temp_csv_root), 'zip', temp_csv_root)
        try:
            shutil.rmtree(temp_csv_root)
        except:
            pass

    # 5. 保存并生成报告
    save_history(local_history)
    report_file = report_history_dir / f"report_{ts_folder}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"SISR 分析报告 ({ts_human})\n" + "=" * 60 + "\n\n")
        f.write(f"🌟【Part 1】优于 BKS ({len(bks_breakers)}):\n" + "-" * 60 + "\n")
        f.write("\n".join(bks_breakers) if bks_breakers else "无")
        f.write(f"\n\n🚀【Part 2】本地提升 ({len(local_only_improvements)}):\n" + "-" * 60 + "\n")
        f.write("\n".join(local_only_improvements) if local_only_improvements else "无")

    log_with_time(f"✨ 周期任务完成。报告: {report_file.name}")


def main():
    log_with_time("🚀 系统启动...")
    while True:
        try:
            run_cycle()
            log_with_time(f"💤 休眠中。下次运行约在 24 小时后。")
            time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_with_time(f"❌ 异常: {e}\n将在 60 秒后重试...")
            time.sleep(60)


if __name__ == "__main__":
    main()