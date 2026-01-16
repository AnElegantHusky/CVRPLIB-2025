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
EXPORT_CSV = True
CSV_EXCLUDE_COLUMNS = ["solution"]
PROCESS_KEYWORD = "main_for_all_final.py"

# 团队名称定义
Our_team = 'OptVerse-CityU'

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
            log_with_time(f"🧹 已清理旧数据: {dir_path.name}")
        except Exception as e:
            log_with_time(f"⚠️ 清理 {dir_path.name} 失败: {e}")
    dir_path.mkdir(parents=True, exist_ok=True)


def get_cvrplib_instances_float():
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"
    headers = {"User-Agent": "Mozilla/5.0"}
    log_with_time("🌍 正在从 CVRPLIB 获取最新 BKS 榜单及 Leader 信息...")
    try:
        response = requests.get(target_url, headers=headers, timeout=20, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('main section table')
        data_dict = {}
        for row in table.find('tbody').find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 3:
                key = cols[0].get_text(strip=True)
                leader_team = cols[1].get_text(strip=True)
                raw_val = cols[2].get_text(strip=True)
                try:
                    clean_val = raw_val.replace('$', '').replace(',', '').replace('{', '').replace('}', '')
                    # 存储 score 和 leader
                    data_dict[key] = {"score": float(clean_val), "leader": leader_team}
                except:
                    continue
        log_with_time(f"✅ 获取成功，共加载 {len(data_dict)} 个算例。")
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
    server_status_report = []
    active_servers, down_servers, error_servers, total_processes = 0, 0, 0, 0

    current_db_buffer = LOCAL_ROOT / "log_buffer"
    csv_save_path = LOCAL_ROOT / "latest_csvs"
    if not SAVE_ALL_HISTORY:
        clean_old_data(current_db_buffer)
        if EXPORT_CSV: clean_old_data(csv_save_path)

    sol_history_dir = LOCAL_ROOT / "all_history_sols" / f"sol_{ts_folder}"
    report_history_dir = LOCAL_ROOT / "all_history_reports"
    sol_history_dir.mkdir(parents=True, exist_ok=True)
    report_history_dir.mkdir(parents=True, exist_ok=True)

    log_with_time(f"🚀 周期开始: {ts_human} (CSV导出: {'开启' if EXPORT_CSV else '关闭'})")

    # 1. 抓取与监控 (保持不变)
    for srv in SERVERS:
        try:
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']}, connect_timeout=10) as conn:
                cp = conn.run(f"ps -ef | grep '{PROCESS_KEYWORD}' | grep -v grep | wc -l", hide=True)
                n = int(cp.stdout.strip())
                if n > 0:
                    status_msg = f"✅ Running ({n})"
                    active_servers += 1
                    total_processes += n
                else:
                    status_msg = "❌ DOWN"
                    down_servers += 1
                server_status_report.append(f"🖥️ {srv['host']}: {status_msg}")
                remote_root = f"{srv['base_path'].rstrip('/')}/log_buffer"
                res = conn.run(f"find {remote_root} -name 'shared.db'", hide=True, warn=True)
                if res.ok and res.stdout.strip():
                    for remote_f in res.stdout.strip().split('\n'):
                        inst = remote_f.split('/')[-2]
                        local_f = current_db_buffer / inst / "shared.db"
                        local_f.parent.mkdir(parents=True, exist_ok=True)
                        conn.get(remote_f, local=str(local_f))
            log_with_time(f"  [Fetch OK] {srv['host']} (Found {n} processes)")
        except Exception as e:
            server_status_report.append(f"🖥️ {srv['host']}: ⚠️ Error: {e}")
            error_servers += 1
            log_with_time(f"  [Fetch Error] {srv['host']}: {e}")

    print("-" * 50)
    log_with_time("📊 采集完毕。开始数据分析...")

    # 2. 数据分析
    local_history = load_history()
    bks_breakers, local_improvements, exact_matches, not_broken_gaps = [], [], [], []

    for db_p in current_db_buffer.rglob("shared.db"):
        inst_name = db_p.parent.name
        try:
            with sqlite3.connect(db_p) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # CSV 导出逻辑 (略，保持不变)
                if EXPORT_CSV:
                    csv_dir = csv_save_path / inst_name
                    csv_dir.mkdir(parents=True, exist_ok=True)
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                    for tbl in [t[0] for t in cursor.fetchall()]:
                        cursor.execute(f"SELECT * FROM {tbl}")
                        rs = cursor.fetchall()
                        if rs:
                            all_cols = list(rs[0].keys())
                            filtered_cols = [c for c in all_cols if c not in CSV_EXCLUDE_COLUMNS]
                            with open(csv_dir / f"{tbl}.csv", 'w', newline='', encoding='utf-8') as f:
                                w = csv.writer(f)
                                w.writerow(filtered_cols)
                                for r in rs: w.writerow([r[c] for c in filtered_cols])

                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    bks_info = leaderboard_data.get(inst_name, {})
                    bks_v = bks_info.get("score")
                    leader = bks_info.get("leader", "Unknown")
                    old_v = local_history.get(inst_name)

                    # 格式化 Leader 名称，如果是自己则加个星号或显示为 Our
                    leader_str = f"[{leader}]" if leader != Our_team else f"[*Ours*]"

                    is_breaking = (bks_v is not None and score < bks_v)
                    is_exact = (bks_v is not None and abs(score - bks_v) < 1e-6)
                    is_improving = (old_v is None or score < old_v)

                    if is_breaking:
                        gap = bks_v - score
                        msg = f"🏆 [NEW RECORD] {inst_name} | Our: {score:.4f} < BKS: {bks_v:.4f} (Gap: -{gap:.4f}) | Leader: {leader_str}"
                        bks_breakers.append({"name": inst_name, "msg": msg})
                        log_with_time(msg)
                        if is_improving: local_history[inst_name] = score
                    elif is_exact:
                        msg = f"🎯 [Exact Match] {inst_name} | Our: {score:.4f} / BKS: {bks_v:.4f} | Gap: 0.000 (0.000%) | Leader: {leader_str}"
                        exact_matches.append({"name": inst_name, "msg": msg})
                        log_with_time(msg)
                        if is_improving: local_history[inst_name] = score
                    else:
                        if bks_v is not None:
                            gap = score - bks_v
                            gap_p = (gap / bks_v)
                            msg = f"⏳ {inst_name} | Our: {score:.4f} / BKS: {bks_v:.4f} | Gap: +{gap:.4f} (+{gap_p * 100:.3f}%) | Leader: {leader_str}"
                            not_broken_gaps.append({"name": inst_name, "gap_v": gap_p, "msg": msg})

                        if is_improving:
                            local_history[inst_name] = score
                            imp_val = 0 if old_v is None else old_v - score
                            msg = f"📈 [Self Improved] {inst_name} | Now: {score:.4f} (Improved: -{imp_val:.4f})"
                            local_improvements.append({"name": inst_name, "msg": msg})
                            log_with_time(msg)

                    with open(sol_history_dir / f"{inst_name}.sol", 'w', encoding='utf-8') as f:
                        for i, r in enumerate(ast.literal_eval(row['solution'])):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")
        except Exception as e:
            log_with_time(f"  [Process Error] {inst_name}: {e}")

    # 排序及保存报告 (保持原有 Part 1-5 结构)
    bks_breakers.sort(key=lambda x: extract_n_value(x['name']))
    local_improvements.sort(key=lambda x: extract_n_value(x['name']))
    exact_matches.sort(key=lambda x: extract_n_value(x['name']))
    not_broken_gaps.sort(key=lambda x: x['gap_v'])

    save_history(local_history)
    rep_p = report_history_dir / f"report_{ts_folder}.txt"
    with open(rep_p, 'w', encoding='utf-8') as f:
        f.write(f"SISR 自动巡检报告 ({ts_human})\n" + "=" * 60 + "\n\n")
        f.write(f"📊 【汇总概要】\n* 服务器在线率: {active_servers} / {len(SERVERS)}\n* 总活跃进程数: {total_processes}\n")
        if down_servers > 0: f.write(f"* 🛑 离线警告: 有 {down_servers} 台停止运行！\n")
        f.write("-" * 60 + "\n\n")
        f.write("📡 【Part 1】服务器状态详情:\n" + "-" * 60 + "\n" + "\n".join(server_status_report) + "\n\n")
        f.write(f"🌟 【Part 2】New Records ({len(bks_breakers)}):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in bks_breakers]) + "\n\n")
        f.write(f"🚀 【Part 3】Self Improved ({len(local_improvements)}):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in local_improvements]) + "\n\n")
        f.write(f"🎯 【Part 4】Exact BKS Match ({len(exact_matches)}):\n" + "-" * 60 + "\n" + "\n".join(
            [x['msg'] for x in exact_matches]) + "\n\n")
        f.write(
            f"📊 【Part 5】未突破 BKS 的差距排行:\n" + "-" * 60 + "\n" + "\n".join([x['msg'] for x in not_broken_gaps]))

    log_with_time(f"✨ 周期结束。报告已保存: {rep_p.name}")


def main():
    log_with_time(f"🚀 系统启动。每 {FETCH_INTERVAL / 3600} 小时自动巡检一次...")
    while True:
        try:
            run_cycle()
            log_with_time(f"💤 任务休眠，下次巡检在 {FETCH_INTERVAL / 3600} 小时后。")
            time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log_with_time(f"❌ 异常: {e}");
            time.sleep(60)


if __name__ == "__main__":
    main()