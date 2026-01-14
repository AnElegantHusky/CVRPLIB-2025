import os
import time
import sqlite3
import csv
import json
import shutil
import ast
import requests
import re
from datetime import datetime
from pathlib import Path
from fabric import Connection
from bs4 import BeautifulSoup

# ================= 配置区域 =================
SAVE_ALL_HISTORY = False
EXPORT_CSV = False
PROCESS_KEYWORD = "main_for_all_final.py"       # TODO： 这里的脚本名可能要查一下，这里是查看程序是否还在运行。

# 查看时，登录一个服务器，然后尝试 ps -ef | grep python 或 ps -ef | grep python3，看看文件名，然后填写在 PROCESS_KEYWORD

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

FETCH_INTERVAL = 2 * 3600
LOCAL_ROOT = Path(__file__).resolve().parent
HISTORY_FILE = LOCAL_ROOT / "best_scores_history.json"


# ================= 工具函数 =================

def log_with_time(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def extract_n_value(name):
    """从 instance 名字中提取 n 后的数字，用于排序"""
    match = re.search(r'-n(\d+)-', name)
    return int(match.group(1)) if match else 99999


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
        except:
            pass
    dir_path.mkdir(parents=True, exist_ok=True)


def get_cvrplib_instances_float():
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(target_url, headers=headers, timeout=20, verify=False)
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
        return data_dict
    except:
        return {}


# ================= 核心工作流 =================

def run_cycle():
    now = datetime.now()
    ts_folder = now.strftime("%Y%m%d_%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")

    leaderboard_data = get_cvrplib_instances_float()
    server_status_report = []

    current_db_buffer = LOCAL_ROOT / "log_buffer"
    if not SAVE_ALL_HISTORY:
        clean_old_data(current_db_buffer)

    current_db_buffer.mkdir(parents=True, exist_ok=True)
    sol_history_dir = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    report_history_dir = LOCAL_ROOT / "all_history_reports"
    sol_history_dir.mkdir(parents=True, exist_ok=True)
    report_history_dir.mkdir(parents=True, exist_ok=True)

    log_with_time(f"🚀 周期开始: {ts_human}")

    # 1. 抓取与存活检查
    for srv in SERVERS:
        status_str = f"🖥️ {srv['host']}: "
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                check_proc = conn.run(f"ps -ef | grep '{PROCESS_KEYWORD}' | grep -v grep | wc -l", hide=True)
                proc_count = int(check_proc.stdout.strip())
                status_str += f"✅ Running ({proc_count})" if proc_count > 0 else "❌ DOWN"

                remote_log_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                result = conn.run(f"find {remote_log_root} -name 'shared.db'", hide=True, warn=True)
                if result.ok and result.stdout.strip():
                    for remote_file in result.stdout.strip().split('\n'):
                        instance_name = remote_file.split('/')[-2]
                        local_path = current_db_buffer / instance_name / "shared.db"
                        local_path.parent.mkdir(parents=True, exist_ok=True)
                        conn.get(remote_file, local=str(local_path))
        except Exception as e:
            status_str += f"⚠️ Error: {e}"
        server_status_report.append(status_str)

    # 2. 数据分析
    local_history = load_history()
    bks_breakers_list = []  # 改为存储对象以便排序
    local_improvements_list = []
    not_broken_gaps = []

    for db_path in current_db_buffer.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    old_local_best = local_history.get(instance_name)
                    bks_val = leaderboard_data.get(instance_name)

                    is_breaking_bks = (bks_val is not None and score < bks_val)
                    is_improved_locally = (old_local_best is None or score < old_local_best)

                    if is_breaking_bks:
                        bks_breakers_list.append({
                            "name": instance_name,
                            "msg": f"🏆 [NEW RECORD] {instance_name} | Our: {score:.4f} < BKS: {bks_val:.4f} (Gap: -{bks_val - score:.4f})"
                        })
                        if is_improved_locally: local_history[instance_name] = score
                    else:
                        if bks_val is not None:
                            abs_gap = score - bks_val
                            gap_percent = (abs_gap / bks_val) * 100
                            not_broken_gaps.append({
                                "name": instance_name,
                                "msg": f"⏳ {instance_name} | Our: {score:.4f} / BKS: {bks_val:.4f} | Gap: +{abs_gap:.4f} (+{gap_percent:.3f}%)",
                                "gap_val": gap_percent  # 按百分比排序更科学
                            })

                        if is_improved_locally:
                            local_history[instance_name] = score
                            local_improvements_list.append({
                                "name": instance_name,
                                "msg": f"📈 [Self Improved] {instance_name} | Now: {score:.4f}"
                            })

                    # 保存 .sol
                    routes = ast.literal_eval(row['solution'])
                    with open(sol_history_dir / f"{instance_name}.sol", 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except:
            pass

    # --- 执行排序逻辑 ---
    # Part 2 & 3 按 n 值从小到大排
    bks_breakers_list.sort(key=lambda x: extract_n_value(x['name']))
    local_improvements_list.sort(key=lambda x: extract_n_value(x['name']))
    # Part 4 按差距百分比从小到大排
    not_broken_gaps.sort(key=lambda x: x['gap_val'])

    # 3. 生成报告
    save_history(local_history)
    report_file = report_history_dir / f"report_{ts_folder}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"SISR 自动巡检报告 ({ts_human})\n" + "=" * 60 + "\n\n")

        f.write(f"📡 【Part 1】服务器状态:\n" + "-" * 60 + "\n")
        f.write("\n".join(server_status_report) + "\n\n")

        f.write(f"🌟 【Part 2】New Records (按规模n排序) ({len(bks_breakers_list)}):\n" + "-" * 60 + "\n")
        f.write("\n".join([x['msg'] for x in bks_breakers_list]) if bks_breakers_list else "暂无\n")

        f.write(f"\n\n🚀 【Part 3】Self Improved (按规模n排序) ({len(local_improvements_list)}):\n" + "-" * 60 + "\n")
        f.write("\n".join([x['msg'] for x in local_improvements_list]) if local_improvements_list else "暂无\n")

        f.write(f"\n\n📊 【Part 4】未突破 BKS 的差距排行 (按 Gap% 排序):\n" + "-" * 60 + "\n")
        f.write("\n".join([x['msg'] for x in not_broken_gaps]) if not_broken_gaps else "暂无\n")

    log_with_time(f"✨ 巡检完成，报告: {report_file.name}")


def main():
    while True:
        try:
            run_cycle()
        except Exception as e:
            log_with_time(f"Error in main: {e}")
        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()