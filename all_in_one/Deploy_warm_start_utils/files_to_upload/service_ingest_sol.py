import time
import os
import vrplib
import sqlite3
import re
import logging  # <--- 引入日志模块
from pathlib import Path
from datetime import datetime
from write_outer_sol import save_best

# === 配置区域 ===
BASE_PATH = Path(__file__).resolve().parent
DB_ROOT_DIR = BASE_PATH / 'log_buffer'
LOG_FILE_PATH = BASE_PATH / "service_ingest.log"  # <--- 日志文件路径

# 定义监听源列表
SOURCE_DIRS = [
    {"path": "warm_start_outer_sol", "algo_name": "warm_start"},
    {"path": "mahdi_outer_sol", "algo_name": "mahdi"},
]

# === 1. 配置日志系统 (这是核心修改) ===
# 同时输出到文件 和 控制台
logger = logging.getLogger("IngestService")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(message)s')  # 我们自己控制格式，这里只输出内容

# A. 文件句柄 (File Handler) - 自动追加写入
file_handler = logging.FileHandler(LOG_FILE_PATH, mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

# B. 控制台句柄 (Stream Handler) - 输出到屏幕
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)


def is_valid_instance_name(name):
    return re.match(r'^[a-zA-Z0-9_-]+$', name) is not None


def get_current_bks(db_path):
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        row = cursor.execute("SELECT score FROM global_best WHERE id=1").fetchone()
        conn.close()
        if row: return row[0]
        return float('inf')
    except:
        return "?"


def log_status(instance, new_score, old_bks, status, algo_label):
    """
    使用 logger 记录，这样既会在屏幕显示，也会存入 log 文件
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_s_str = f"{new_score:.2f}" if isinstance(new_score, (int, float)) else str(new_score)
    old_s_str = f"{old_bks:.2f}" if isinstance(old_bks, (int, float)) else str(old_bks)

    log_msg = (
        f"[{now_str}] [{algo_label:<10}] {instance:<20} | "
        f"New: {new_s_str:>10} vs BKS: {old_s_str:>10} | "
        f"State: {status}"
    )
    logger.info(log_msg)  # <--- 使用 logger.info 代替 print


def ingest_loop():
    logger.info(f"[*] 启动多源解吸入服务 (Multi-Source Ingest Service)")
    logger.info(f"[*] 日志文件路径: {LOG_FILE_PATH}")
    logger.info(f"[*] 数据库根目录: {DB_ROOT_DIR}")

    monitor_paths = []
    for src in SOURCE_DIRS:
        folder_path = BASE_PATH / src["path"]
        folder_path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(folder_path, 0o777)
        except:
            pass

        monitor_paths.append({
            "path": folder_path,
            "algo_name": src["algo_name"]
        })
        logger.info(f"    监听中: {folder_path}")

    while True:
        batch_processed_count = 0

        for source in monitor_paths:
            src_dir = source["path"]
            algo_label = source["algo_name"]
            sol_files = sorted(list(src_dir.glob("*.sol")))

            for sol_path in sol_files:
                instance_name = sol_path.stem

                # Check 1
                if not is_valid_instance_name(instance_name):
                    logger.warning(f"[Warn] 非法文件名，删除: {sol_path.name}")
                    try:
                        os.remove(sol_path)
                    except:
                        pass
                    continue

                # Check 2
                target_db = DB_ROOT_DIR / instance_name / 'shared.db'
                if not target_db.exists():
                    try:
                        os.remove(sol_path)
                    except:
                        pass
                    continue

                # Process
                try:
                    sol_data = vrplib.read_solution(str(sol_path))
                    cost = sol_data.get('Cost') or sol_data.get('cost')
                    routes = sol_data.get('routes')

                    if cost is None or routes is None:
                        raise ValueError("缺少 Cost 或 routes")

                    current_bks = get_current_bks(target_db)

                    # 写入重试
                    max_retries = 5
                    write_success = False
                    for attempt in range(max_retries):
                        try:
                            updated = save_best(target_db, -1, cost, routes, algo_label)
                            status = "✅ WROTE_DB (Better)" if updated else "⏭️  SKIPPED (Not Better)"

                            log_status(instance_name, cost, current_bks, status, algo_label)

                            write_success = True
                            batch_processed_count += 1
                            break
                        except sqlite3.OperationalError as e:
                            if "locked" in str(e):
                                if attempt == max_retries - 1:
                                    log_status(instance_name, cost, current_bks, "🔒 LOCKED_FAIL", algo_label)
                                else:
                                    time.sleep(0.2 * (attempt + 1))
                                    continue
                            else:
                                raise e

                    if not write_success: continue
                    os.remove(sol_path)

                except Exception as e:
                    logger.error(f"[Error] 处理失败 {sol_path.name}: {e}")
                    try:
                        os.remove(sol_path)
                    except:
                        pass

        if batch_processed_count > 0:
            sep = "-" * 80
            summary = f"Batch Finished at {datetime.now().strftime('%H:%M:%S')} | Processed: {batch_processed_count}"
            end_sep = "=" * 80 + "\n"

            logger.info(sep)
            logger.info(summary)
            logger.info(end_sep)
            time.sleep(0.5)
        else:
            time.sleep(2)


if __name__ == "__main__":
    try:
        ingest_loop()
    except KeyboardInterrupt:
        logger.info("\n[*] 服务已停止")