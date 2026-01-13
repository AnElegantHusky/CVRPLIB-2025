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
SAVE_ALL_HISTORY = False  # True: 保存所有历史数据; False: DB和CSV只保留最新

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
    if dir_path.exists():
        try:
            shutil.rmtree(dir_path, ignore_errors=False)
            log_with_time(f"🧹 已清理旧目录: {dir_path.name}")
        except Exception as e:
            log_with_time(f"⚠️ 清理目录 {dir_path.name} 失败 (可能文件被占用): {e}")
    dir_path.mkdir(parents=True, exist_ok=True)


# ================= 爬虫工具函数 =================

def get_cvrplib_instances_float():
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    log_with_time("🌍 正在连接 CVRPLIB 获取最新世界纪录(BKS)...")
    try:
        response = requests.get(target_url, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        table = soup.select_one('main section table')
        if not table:
            table = soup.find('table')

        if not table:
            log_with_time("⚠️ 未找到榜单表格，跳过 BKS 对比。")
            return {}

        data_dict = {}
        tbody = table.find('tbody')

        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    key = cols[0].get_text(strip=True)
                    raw_value = cols[2].get_text(strip=True)
                    try:
                        clean_value = raw_value.replace('$', '').replace(',', '').replace('{', '').replace('}', '')
                        data_dict[key] = float(clean_value)
                    except ValueError:
                        continue

        log_with_time(f"✅ 成功获取榜单数据，共 {len(data_dict)} 条记录。")
        return data_dict

    except Exception as e:
        log_with_time(f"⚠️ 获取榜单失败: {e}")
        return {}


# ================= 核心工作流 =================

def run_cycle():
    now = datetime.now()
    ts_folder = now.strftime("%Y%m%d_%H%M%S")
    ts_human = now.strftime("%Y-%m-%d %H:%M:%S")

    # 0. 获取最新 Leaderboard 数据
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

    log_with_time(f"🚀 周期开始: {ts_human} (历史记录模式: {'开启' if SAVE_ALL_HISTORY else '关闭'})")

    # 2. 抓取 (Fetch) 阶段
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
    log_with_time("✅ 所有服务器采集完毕。开始分析数据...")
    print("-" * 60)

    # 3. 处理数据 & 对比
    local_history = load_history()

    # === 两个分类列表 ===
    bks_breakers = []  # 优于 Leaderboard
    local_only_improvements = []  # 仅优于本地历史

    temp_csv_root = csv_save_path / f"csv_{ts_folder}"
    temp_csv_root.mkdir(parents=True, exist_ok=True)

    for db_path in current_db_buffer.rglob("shared.db"):
        instance_name = db_path.parent.name
        try:
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                # A. 转换 CSV
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

                # B. 提取最佳解并对比
                cursor.execute("SELECT solution, score FROM global_best WHERE id = 1;")
                row = cursor.fetchone()
                if row and row['solution']:
                    score = float(row['score'])
                    old_local_best = local_history.get(instance_name)
                    bks_val = leaderboard_data.get(instance_name)

                    # 判断逻辑：是否打破了本地记录？
                    if old_local_best is None or score < old_local_best:
                        # 1. 首先更新本地历史，防止下次重复报告
                        local_history[instance_name] = score

                        # 2. 计算本地提升幅度
                        local_diff = 0 if old_local_best is None else old_local_best - score

                        # 3. 分类：是打破 BKS 还是仅本地提升？
                        is_bks_broken = False
                        if bks_val is not None and score < bks_val:
                            is_bks_broken = True

                        if is_bks_broken:
                            gap = bks_val - score
                            msg = f"🏆 [NEW RECORD] {instance_name} | Our: {score:.4f} < BKS: {bks_val:.4f} (Gap: -{gap:.4f})"
                            bks_breakers.append(msg)
                            log_with_time(msg)  # 控制台高亮
                        else:
                            # 仅本地提升
                            msg = f"📈 [Self Improved] {instance_name} | Now: {score:.4f} (Improved: -{local_diff:.4f})"
                            # 如果有 BKS 数据，顺便显示一下距离 BKS 还有多远
                            if bks_val:
                                gap_to_bks = score - bks_val
                                msg += f" | Gap to BKS: +{gap_to_bks:.4f}"

                            local_only_improvements.append(msg)
                            log_with_time(msg)  # 控制台输出

                    # 4. 无论是否破纪录，保存 .sol 文件以供查阅
                    routes = ast.literal_eval(row['solution'])
                    sol_file = sol_history_dir / f"{instance_name}.sol"
                    with open(sol_file, 'w', encoding='utf-8') as f:
                        for i, r in enumerate(routes):
                            f.write(f"Route #{i + 1}: {' '.join(map(str, r))}\n")
                        f.write(f"Cost {score:.6f}\n")

        except Exception as e:
            log_with_time(f"  [Process Error] {instance_name}: {e}")

    # 4. 打包清理
    if any(temp_csv_root.iterdir()):
        shutil.make_archive(str(temp_csv_root), 'zip', temp_csv_root)
        try:
            shutil.rmtree(temp_csv_root)
        except:
            pass

    # 5. 保存历史及生成战报 (分两部分输出)
    save_history(local_history)

    report_file = report_history_dir / f"report_{ts_folder}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(f"SISR 自动化分析报告 ({ts_human})\n")
        f.write("=" * 60 + "\n\n")

        # 第一部分：优于 BKS
        if bks_breakers:
            f.write(f"🌟【Part 1】优于 Leaderboard (BKS) 的结果 ({len(bks_breakers)} 个):\n")
            f.write("-" * 60 + "\n")
            f.write("\n".join(bks_breakers))
            f.write("\n\n")
        else:
            f.write("🌟【Part 1】本次无优于 Leaderboard 的新纪录。\n\n")

        # 第二部分：仅优于本地历史
        if local_only_improvements:
            f.write(f"🚀【Part 2】仅优于本地历史 (Self Improvement) 的结果 ({len(local_only_improvements)} 个):\n")
            f.write("-" * 60 + "\n")
            f.write("\n".join(local_only_improvements))
            f.write("\n")
        else:
            f.write("🚀【Part 2】本次无本地分数提升。\n")

    log_with_time(f"✨ 周期任务完成。报告已生成: {report_file.name}")
    if bks_breakers:
        log_with_time(f"🔥 ！！！注意！！！ 发现 {len(bks_breakers)} 个世界纪录级别的新解，请立即查看报告！")


# ================= 主入口 =================

def main():
    log_with_time(f"🚀 系统启动。正在进入 {FETCH_INTERVAL // 3600} 小时一次的巡检模式...")
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