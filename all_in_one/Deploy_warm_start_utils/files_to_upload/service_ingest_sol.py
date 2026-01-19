import time
import os
import vrplib
import sqlite3
import re
from pathlib import Path
# 假设 write_outer_sol 在同一目录下，如果不是请调整 import
from write_outer_sol import save_best

# === 配置区域 ===
BASE_PATH = Path(__file__).resolve().parent
DB_ROOT_DIR = BASE_PATH / 'log_buffer'

# 定义监听源列表
SOURCE_DIRS = [
    {"path": "warm_start_outer_sol", "algo_name": "warm_start"},
    {"path": "mahdi_outer_sol", "algo_name": "mahdi"},
]


def is_valid_instance_name(name):
    """
    安全检查：确保实例名只包含安全字符 (字母, 数字, -, _)
    防止路径遍历攻击或非法文件名
    """
    return re.match(r'^[a-zA-Z0-9_-]+$', name) is not None


def ingest_loop():
    print(f"[*] 启动多源解吸入服务 (Multi-Source Ingest Service)")
    print(f"[*] 数据库根目录: {DB_ROOT_DIR}")

    # 1. 初始化所有目录
    monitor_paths = []
    for src in SOURCE_DIRS:
        folder_path = BASE_PATH / src["path"]
        folder_path.mkdir(parents=True, exist_ok=True)
        # 确保目录权限开放，方便接收 (可选)
        try:
            os.chmod(folder_path, 0o777)
        except:
            pass

        monitor_paths.append({
            "path": folder_path,
            "algo_name": src["algo_name"]
        })
        print(f"    监听中: {folder_path} -> 标记为 [{src['algo_name']}]")

    while True:
        has_processed_any = False

        for source in monitor_paths:
            src_dir = source["path"]
            algo_label = source["algo_name"]

            # 使用 glob 匹配 .sol，天然忽略 .tmp 文件
            # 排序是为了处理顺序确定（可选）
            sol_files = sorted(list(src_dir.glob("*.sol")))

            for sol_path in sol_files:
                instance_name = sol_path.stem  # 获取文件名 (无后缀)

                # --- [安全检查 1] 文件名合法性 ---
                if not is_valid_instance_name(instance_name):
                    print(f"[Warn] 非法文件名，直接删除: {sol_path.name}")
                    try:
                        os.remove(sol_path)
                    except:
                        pass
                    continue

                # --- [安全检查 2] 目标 DB 是否存在 ---
                target_db = DB_ROOT_DIR / instance_name / 'shared.db'
                if not target_db.exists():
                    print(f"[Skip] 对应实例DB不存在 (可能非本节点任务): {instance_name}")
                    # 既然没地放，留着也是垃圾，删掉
                    try:
                        os.remove(sol_path)
                    except:
                        pass
                    continue

                # --- 开始处理 ---
                try:
                    # 读取解文件
                    # 注意：vrplib.read_solution 有时对格式要求严格，如果报错会进 except
                    sol_data = vrplib.read_solution(str(sol_path))
                    cost = sol_data.get('Cost') or sol_data.get('cost')
                    routes = sol_data.get('routes')

                    if cost is None or routes is None:
                        raise ValueError("解析失败: 缺少 Cost 或 routes 字段")

                    # --- [关键修改] 数据库写入重试机制 ---
                    # 应对 "database is locked"
                    max_retries = 5
                    write_success = False

                    for attempt in range(max_retries):
                        try:
                            # running_time = -1 表示外部解
                            updated = save_best(target_db, -1, cost, routes, algo_label)
                            if updated:
                                print(f"[Update] [{algo_label}] {instance_name} 成功入库! Score: {cost}")
                            # else:
                            #     print(f"[Skip] [{algo_label}] {instance_name} 未优于现有解")

                            write_success = True
                            break  # 写入成功，跳出重试循环

                        except sqlite3.OperationalError as e:
                            if "locked" in str(e):
                                time.sleep(0.2 * (attempt + 1))  # 线性退避
                                continue
                            else:
                                raise e  # 其他数据库错误直接抛出
                        except Exception as e:
                            raise e

                    if not write_success:
                        print(f"[Error] [{algo_label}] {instance_name} DB 锁定超时，放弃本次写入，保留文件稍后重试。")
                        has_processed_any = True
                        continue  # 跳过删除文件步骤，保留文件下次再试！

                    # --- [最后一步] 处理成功后才删除 ---
                    os.remove(sol_path)
                    has_processed_any = True

                except Exception as e:
                    print(f"[Error] 处理文件失败 {sol_path.name}: {e}")
                    # 如果是解析格式错误，留着也没用，删掉防止死循环
                    # 如果你想保留坏文件排查，可以 move 到一个 bad_files 文件夹
                    try:
                        os.remove(sol_path)
                    except:
                        pass

        # 动态休眠：如果刚才处理了任务，可能还有堆积，歇短点；否则歇长点
        if has_processed_any:
            time.sleep(2)
        else:
            time.sleep(10)


if __name__ == "__main__":
    # 捕获 ctrl+c
    try:
        ingest_loop()
    except KeyboardInterrupt:
        print("\n[*] 服务已停止")