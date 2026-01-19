import time
import os
import vrplib
from pathlib import Path
from write_outer_sol import save_best

# === 配置区域 ===
BASE_PATH = Path(__file__).resolve().parent
DB_ROOT_DIR = BASE_PATH / 'log_buffer'

# 定义监听源列表
# path: 文件夹名称 (相对于 BASE_PATH)
# algo_name: 写入数据库时标记的来源名称
SOURCE_DIRS = [
    {"path": "warm_start_outer_sol", "algo_name": "warm_start"},
    {"path": "mahdi_outer_sol", "algo_name": "mahdi"},
    # 你可以在这里继续添加其他来源
    # {"path": "another_folder", "algo_name": "another_algo"},
]


def ingest_loop():
    print(f"[*] 启动多源解吸入服务 (Multi-Source Ingest Service)")

    # 1. 初始化所有目录
    monitor_paths = []
    for src in SOURCE_DIRS:
        folder_path = BASE_PATH / src["path"]
        folder_path.mkdir(parents=True, exist_ok=True)
        # 将解析后的绝对路径存回去，避免循环里重复计算
        monitor_paths.append({
            "path": folder_path,
            "algo_name": src["algo_name"]
        })
        print(f"    监听中: {folder_path} -> 标记为 [{src['algo_name']}]")

    print(f"    数据库根目录: {DB_ROOT_DIR}")

    while True:
        has_processed_files = False

        # 2. 轮询所有源文件夹
        for src in monitor_paths:
            current_dir = src["path"]
            algo_label = src["algo_name"]

            # 获取文件列表
            try:
                sol_files = list(current_dir.glob('*.sol'))
            except Exception as e:
                print(f"[Scan Error] {current_dir}: {e}")
                continue

            if not sol_files:
                continue

            has_processed_files = True

            for sol_path in sol_files:
                try:
                    instance_name = sol_path.stem  # 文件名即实例名 (例如 XL-001)

                    # A. 读取解文件
                    sol_data = vrplib.read_solution(str(sol_path))
                    cost = sol_data.get('cost')
                    routes = sol_data.get('routes')

                    if cost is None or routes is None:
                        print(f"[Warn] 格式错误，删除: {sol_path.name}")
                        os.remove(sol_path)
                        continue

                    # B. 定位数据库
                    # 假设结构: log_buffer/XL-001/shared.db
                    target_db = DB_ROOT_DIR / instance_name / 'shared.db'

                    if not target_db.exists():
                        # 如果是新实例，可能需要创建目录，或者仅仅跳过
                        # 这里选择跳过并删除文件，防止堆积
                        print(f"[Warn] DB不存在，跳过: {instance_name}")
                        os.remove(sol_path)
                        continue

                    # C. 写入数据库
                    # running_time 设为 -1 表示外部导入
                    updated = save_best(target_db, -1, cost, routes, algo_label)

                    if updated:
                        print(f"[Update] [{algo_label}] {instance_name} 更新成功! Score: {cost}")
                    # else:
                    #     print(f"[Skip] [{algo_label}] {instance_name} 未优于当前解")

                except Exception as e:
                    print(f"[Error] 处理 {sol_path.name} ({algo_label}) 失败: {e}")

                finally:
                    # D. 无论成功失败，务必删除文件
                    if sol_path.exists():
                        try:
                            os.remove(sol_path)
                        except OSError:
                            pass

        # 动态调整休眠时间
        # 如果刚才处理了文件，说明可能正忙，休眠短一点；否则休眠长一点
        time.sleep(60)


if __name__ == "__main__":
    try:
        ingest_loop()
    except KeyboardInterrupt:
        print("\n[*] 服务停止")