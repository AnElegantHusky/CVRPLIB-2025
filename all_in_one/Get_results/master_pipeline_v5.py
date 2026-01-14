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
# 1. 功能开关
SAVE_ALL_HISTORY = False
EXPORT_CSV = False

# 2. CSV 导出自定义：在此列表填入你【不想】在 CSV 中看到的列名
# 例如：["solution"] 会把巨大的路径字符串删掉，让 CSV 变清爽
CSV_EXCLUDE_COLUMNS = ["solution"]      # TODO 看看csv里solution列的表头是什么，然后将要删除的表头放进来

# 3. 进程监测配置
PROCESS_KEYWORD = "main_for_all_final.py"       # TODO

# 查看时，登录一个服务器，然后尝试 ps -ef | grep python 或 ps -ef | grep python3，看看文件名，然后填写在 PROCESS_KEYWORD

# 4. 服务器清单 (保持不变)
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

FETCH_INTERVAL = 1 * 3600
LOCAL_ROOT = Path(__file__).resolve().parent
HISTORY_FILE = LOCAL_ROOT / "best_scores_history.json"


# ================= 工具函数 =================

def log_with_time(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def extract_n_value(name):
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
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('main section table')
        data_dict = {}
        for row in table.find('tbody').find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                key = cols[0].get_text(strip=True)
                raw_val = cols[2].get_text(strip=True)
                try:
                    clean_val = raw_val.replace('$', '').replace(',', '').replace('{', '').replace('}', '')
                    data_dict[key] = float(clean_val)
                except:
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
    csv_save_path = LOCAL_ROOT / "latest_csvs"
    if not SAVE_ALL_HISTORY:
        clean_old_data(current_db_buffer)
        if EXPORT_CSV: clean_old_data(csv_save_path)

    sol_history_dir = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    report_history_dir = LOCAL_ROOT / "all_history_reports"
    sol_history_dir.mkdir(parents=True, exist_ok=True)
    report_history_dir.mkdir(parents=True, exist_ok=True)

    log_with_time(f"🚀 巡检开始: {ts_human}")

    # 1. 抓取与监控
    for srv in SERVERS:
        status_str = f"🖥️ {srv['host']}: "
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                cp = conn.run(f"ps -ef | grep '{PROCESS_KEYWORD}' | grep -v grep | wc -l", hide=True)
                n = int(cp.stdout.strip())
                status_str += f"✅ Running ({n})" if n > 0 else "❌ DOWN"

                remote_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                res = conn.run(f"find {remote_root} -name 'shared.db'", hide=True, warn=True)
                if res.ok and res.stdout.strip():
                    for remote_f in res.stdout.strip().split('\n'):
                        inst = remote_f.split('/')[-2]
                        local_f = current_db_buffer / inst / "shared.db"
                        local_f.parent.mkdir(parents=True, exist_ok=True)
                        conn.get(remote_f, local=str(local_f))
        except Exception as e:
            status_str += f"⚠️ Error: {e}"
        server_status_report.append(status_str)

    # 2. 数据分析
    local_history = load_history()
    bks_breakers = []
    local_improvements = []
    not_broken_gaps = []

    for db_p in current_db_buffer.rglob("shared.db"):
        inst_name = db_p.parent.name
        try:
            with sqlite3.connect(db_p) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # --- 导出 CSV (含列过滤逻辑) ---
                if EXPORT_CSV:
                    csv_dir = csv_save_path / inst_name
                    csv_dir.mkdir(parents=True, exist_ok=True)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    for tbl in [t[0] for t in cursor.fetchall()]:
                        cursor.execute(f"SELECT * FROM {tbl}")
                        rs = cursor.fetchall()
                        if rs:
                            # 过滤表头和数据
                            all_cols = list(rs[0].keys())
                            filtered_cols = [c for c in all_cols if c not in CSV_EXCLUDE_COLUMNS]

                            with open(csv_dir / f"{tbl}.csv", 'w', newline='', encoding='utf-8') as f:
                                w = csv.writer(f)
                                w.writerow(filtered_cols)  # 写入过滤后的表头
                                for row in rs:
                                    # 仅写入不在排除列表中的列数据
                                    w.writerow([row[c] for c in filtered_cols])

                # --- 结果对比 ---
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    bks_v = leaderboard_data.get(inst_name)
                    old_v = local_history.get(inst_name)

                    is_breaking = (bks_v is not None and score < bks_v)
                    is_improving = (old_v is None or score < old_v)

                    if is_breaking:
                        bks_breakers.append({"name": inst_name,
                                             "msg": f"🏆 [NEW RECORD] {inst_name} | Our: {score:.4f} < BKS: {bks_v:.4f} (Gap: -{bks_v - score:.4f})"})
                        if is_improving: local_history[inst_name] = score
                    else:
                        if bks_v is not None:
                            gap = score - bks_v
                            not_broken_gaps.append({"name": inst_name, "gap_v": (gap / bks_v),
                                                    "msg": f"⏳ {inst_name} | Our: {score:.4f} / BKS: {bks_v:.4f} | Gap: +{gap:.4f} (+{(gap / bks_v) * 100:.3f}%)"})
                        if is_improving:
                            local_history[inst_name] = score
                            local_improvements.append(
                                {"name": inst_name, "msg": f"📈 [Self Improved] {inst_name} | Now: {score:.4f}"})

                    # 导出 .sol (这个始终导出完整路径用于提交)
                    with open(sol_history_dir / f"{inst_name}.sol", 'w') as f:
                        for i, r in enumerate(ast.literal_eval(row['solution'])):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except:
            pass

    # 排序与写报告 (保持不变)
    bks_breakers.sort(key=lambda x: extract_n_value(x['name']))
    local_improvements.sort(key=lambda x: extract_n_value(x['name']))
    not_broken_gaps.sort(key=lambda x: x['gap_v'])

    save_history(local_history)
    rep_p = report_history_dir / f"report_{ts_folder}.txt"
    with open(rep_p, 'w', encoding='utf-8') as f:
        f.write(f"SISR 自动巡检报告 ({ts_human})\n" + "=" * 60 + "\n\n")
        f.write("📡 【Part 1】服务器状态:\n" + "-" * 60 + "\n" + "\n".join(server_status_report) + "\n\n")
        f.write(f"🌟 【Part 2】New Records (按n排序) ({len(bks_breakers)}):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in bks_breakers]) + "\n\n")
        f.write(f"🚀 【Part 3】Self Improved (按n排序) ({len(local_improvements)}):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in local_improvements]) + "\n\n")
        f.write(f"📊 【Part 4】未突破 Gap 排行 (按Gap%排序):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in not_broken_gaps]))

    log_with_time(f"✨ 巡检完成: {rep_p.name}")


def main():
    while True:
        try:
            run_cycle()
        except Exception as e:
            log_with_time(f"Error: {e}")
        time.sleep(FETCH_INTERVAL)


if __name__ == "__main__":
    main()