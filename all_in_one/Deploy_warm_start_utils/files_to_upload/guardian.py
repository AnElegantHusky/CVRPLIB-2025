import os
import time
import shutil
import subprocess
import glob
import sqlite3
import json
import ast
import re
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool

# ================= 1. 全局配置区域 =================

# --- 路径配置 (根据容器挂载情况修改) ---
# 本地 WarmStart 容器工作区
WS_ROOT = Path("/app/all_in_one/SISR")
WS_INIT_SOLS = WS_ROOT / "init_sols"  # 最终筛选出的初解存放地 (将被 inject 读取)
WS_LOG_BUFFER = WS_ROOT / "log_buffer"  # 本地计算结果 DB
WS_RESULT_DIR = WS_ROOT / "result_sols"  # 最终结果归档

# 远程 CVRPLIB 容器工作区 (挂载点)
CVRPLIB_ROOT = Path("/cvrplib_link/all_in_one/SISR")
CVRPLIB_DB_DIR = CVRPLIB_ROOT / "log_buffer"
# 提取出的解池 (中间产物): Instance/Method/x.sol
CVRPLIB_EXT_POOL = CVRPLIB_ROOT / "ails2_ext_sols"
# 回传给 CVRPLIB 的接收文件夹
CVRPLIB_RECEIVE_DIR = CVRPLIB_ROOT.parent.parent / "warm_start_outer_sol"

# --- 运行配置 ---
WARM_START_DAY = 2
WORKER_SCRIPT = "main_for_all_warm_start.py"

# --- 筛选策略配置 ---
# 提取哪些算法的历史解？(空列表代表提取所有发现的算法)
EXTRACT_ALGOS = []  # e.g. ["ails2", "sisr_cvrp"]

# 筛选优先级: 按顺序查找，找到即止
# 如果首选算法没解，就找备选
FILTER_METHOD_PRIORITY = [
    "ails2_1day",
    "sisr_cvrp",
    "ails2_10day",
    "global_best"  # 特殊保留字，代表直接从 global_best 表拿
]

# 同一方法下选哪个解? "best_score" (分最低) 或 "latest" (rank 1, 最新)
FILTER_CRITERIA = "best_score"


# ================= 2. 模块: 解提取 (Task 1) =================

class HistoryExtractor:
    """
    复用 extract_survivor_history.py 的逻辑
    将 DB 数据转换为文件结构: Pool/Instance/Method/Rank.sol
    """

    @staticmethod
    def parse_solution_text(sol_text):
        if not sol_text: return None
        try:
            return ast.literal_eval(sol_text)
        except:
            try:
                return json.loads(sol_text)
            except:
                return None

    @staticmethod
    def write_sol_file(routes, score, out_path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            for idx, route in enumerate(routes):
                f.write(f"Route #{idx + 1}: {' '.join(map(str, route))}\n")
            f.write(f"Cost {score}\n")

    @staticmethod
    def extract_from_db(db_path, out_base_dir, instance_name):
        """
        从单个 DB 提取解，建立目录结构
        """
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()

            # 1. 获取该 DB 里所有的算法名称 (如果未指定提取列表)
            target_algos = EXTRACT_ALGOS
            if not target_algos:
                try:
                    cursor.execute("SELECT DISTINCT algo_name FROM solution_history")
                    target_algos = [r[0] for r in cursor.fetchall() if r[0]]
                except:
                    target_algos = []

            # 同时也提取 global_best 作为一种特殊的 "method"
            target_algos.append("global_best")

            for algo in target_algos:
                rows = []
                if algo == "global_best":
                    # 特殊处理 global_best 表
                    cursor.execute("SELECT solution, score, 'global_best', 0 FROM global_best WHERE id=1")
                    rows = cursor.fetchall()
                else:
                    # 查询 history 表 (Top 5 最新)
                    try:
                        cursor.execute("""
                            SELECT solution, score, algo_name, runningtime 
                            FROM solution_history 
                            WHERE algo_name = ? 
                            ORDER BY runningtime DESC LIMIT 5
                        """, (algo,))
                        rows = cursor.fetchall()
                    except:
                        pass  # 可能表不存在

                if not rows: continue

                # 写入文件
                # 结构: out_base_dir / Instance / Method / 1.sol (1代表最新/最优)
                for rank, (sol_text, score, _, _) in enumerate(rows, start=1):
                    routes = HistoryExtractor.parse_solution_text(sol_text)
                    if routes:
                        out_path = out_base_dir / instance_name / algo / f"{rank}.sol"
                        HistoryExtractor.write_sol_file(routes, score, out_path)

            conn.close()
            return True
        except Exception as e:
            print(f"   [Extract Error] {instance_name}: {e}")
            return False


# ================= 3. 模块: 解筛选 (Task 2) =================

class SolutionFilter:
    """
    负责从提取出的文件池中，根据策略选出【唯一】初解
    """

    @staticmethod
    def get_sol_cost(file_path):
        """读取文件最后一行获取 Cost"""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
                for line in reversed(lines):
                    if line.strip().startswith("Cost"):
                        return float(line.strip().split()[-1])
        except:
            pass
        return float('inf')

    @staticmethod
    def select_best_for_instance(instance_name, pool_dir):
        """
        输入: 实例名称, 解池根目录
        输出: 选中的最佳 .sol 文件路径
        """
        inst_pool = pool_dir / instance_name
        if not inst_pool.exists():
            return None

        # 1. 按优先级遍历方法
        for method in FILTER_METHOD_PRIORITY:
            method_dir = inst_pool / method
            if not method_dir.exists():
                continue

            # 找到了对应方法的目录，读取下面的所有 .sol
            sol_files = list(method_dir.glob("*.sol"))
            if not sol_files: continue

            # 2. 根据标准选择具体的解文件
            selected_file = None

            if FILTER_CRITERIA == "latest":
                # 文件名是 1.sol, 2.sol... 1 是最新的
                # 简单排序找数字最小的
                sol_files.sort(key=lambda x: int(x.stem))
                selected_file = sol_files[0]

            elif FILTER_CRITERIA == "best_score":
                # 遍历读取分数，选最低的
                best_cost = float('inf')
                for f in sol_files:
                    cost = SolutionFilter.get_sol_cost(f)
                    if cost < best_cost:
                        best_cost = cost
                        selected_file = f

            if selected_file:
                # print(f"   [Filter] {instance_name}: Selected {method}/{selected_file.name} (Cost: {best_cost if 'best_cost' in locals() else '?'})")
                return selected_file

        # 3. 兜底: 如果优先级里的都没找到，随便找一个存在的
        # (例如提取到了 eoh 但不在优先级列表里)
        all_methods = [d for d in inst_pool.iterdir() if d.is_dir()]
        for m in all_methods:
            sols = list(m.glob("*.sol"))
            if sols:
                return sols[0]

        return None


# ================= 4. 任务流程函数 =================

def task_1_extract():
    print(f"Step 1: Extracting history to {CVRPLIB_EXT_POOL}...")
    if CVRPLIB_EXT_POOL.exists():
        # 可选：清理旧池子，保证干净
        # shutil.rmtree(CVRPLIB_EXT_POOL)
        pass

    CVRPLIB_EXT_POOL.mkdir(parents=True, exist_ok=True)

    # 遍历 CVRPLIB 的 DB 目录
    instances = [d for d in CVRPLIB_DB_DIR.iterdir() if d.is_dir() and d.name.startswith("XL")]
    count = 0

    for inst_dir in instances:
        db_path = inst_dir / "shared.db"
        if not db_path.exists(): continue

        # 提取到 Pool/InstanceName/...
        if HistoryExtractor.extract_from_db(db_path, CVRPLIB_EXT_POOL, inst_dir.name):
            count += 1

    print(f"   Extracted solutions for {count} instances.")


def task_2_init_workspace():
    print(f"Step 2: Filtering & Initializing Workspace ({WS_INIT_SOLS})...")

    if WS_INIT_SOLS.exists():
        shutil.rmtree(WS_INIT_SOLS)
    WS_INIT_SOLS.mkdir(parents=True, exist_ok=True)

    # 遍历解池中的实例
    pool_instances = [d for d in CVRPLIB_EXT_POOL.iterdir() if d.is_dir()]

    for inst_dir in pool_instances:
        inst_name = inst_dir.name

        # 筛选
        best_sol = SolutionFilter.select_best_for_instance(inst_name, CVRPLIB_EXT_POOL)

        if best_sol:
            # 准备目标: init_sols/InstanceName/InstanceName.sol
            # 注意：要重命名为 .sol 文件，不要保留 rank.sol 的名字，也不要方法层级
            # 方便 main_for_all 里的 glob 直接找
            target_dir = WS_INIT_SOLS / inst_name
            target_dir.mkdir(parents=True, exist_ok=True)

            # 这里我们重命名为 "init.sol" 或者 "InstanceName.sol"
            # 为了配合 inject_initial_solution 的 glob "**/*.sol"，这里怎么存都可以
            # 但最好带上方法名方便调试
            method_name = best_sol.parent.name
            target_file = target_dir / f"{method_name}_init.sol"

            shutil.copy(best_sol, target_file)


def run_worker_process(instance_name):
    """子进程运行函数"""
    # 构造命令
    cmd = [
        "python3", WORKER_SCRIPT,
        "--instance_name", instance_name,
        "--warm_start_day", str(WARM_START_DAY),
    ]

    try:
        # shell=False (默认), args传列表，这是最稳健的
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (instance_name, True)
    except subprocess.CalledProcessError:
        return (instance_name, False)
    except Exception as e:
        print(f"Worker Error {instance_name}: {e}")
        return (instance_name, False)


def task_3_run_parallel():
    # 扫描 init_sols 确定要跑哪些实例
    if not WS_INIT_SOLS.exists():
        print("No instances initialized!")
        return

    instances = [d.name for d in WS_INIT_SOLS.iterdir() if d.is_dir()]
    print(f"Step 3: Running {len(instances)} instances (Timeout: {WARM_START_DAY}s)...")

    start_t = time.time()

    # 使用 Pool 并发
    # 如果实例很多，可以指定 processes=CPU_COUNT - 1
    with Pool() as p:
        results = p.map(run_worker_process, instances)

    duration = time.time() - start_t
    success_cnt = sum(1 for r in results if r[1])
    print(f"   Finished in {duration:.1f}s. Success: {success_cnt}/{len(instances)}")


def task_4_collect_and_push():
    print("Step 4: Collecting & Pushing Results...")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_save_dir = WS_RESULT_DIR / timestamp
    local_save_dir.mkdir(parents=True, exist_ok=True)

    CVRPLIB_RECEIVE_DIR.mkdir(parents=True, exist_ok=True)

    count = 0
    # 遍历 WS 本地的 log_buffer
    for inst_dir in WS_LOG_BUFFER.iterdir():
        if not inst_dir.is_dir(): continue

        db_path = inst_dir / "shared.db"
        if not db_path.exists(): continue

        # 提取最优解
        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT solution, score FROM global_best WHERE id=1")
            row = cursor.fetchone()
            conn.close()

            if row:
                sol_json, score = row
                try:
                    routes = json.loads(sol_json)
                except:
                    routes = ast.literal_eval(sol_json)

                # 保存文件名: InstanceName.sol
                file_name = f"{inst_dir.name}.sol"

                # 1. 保存到 result_sols (带Cost头)
                local_path = local_save_dir / file_name
                HistoryExtractor.write_sol_file(routes, score, local_path)

                # 2. 复制到外部接收文件夹
                remote_path = CVRPLIB_RECEIVE_DIR / file_name
                shutil.copy(local_path, remote_path)
                count += 1
        except Exception as e:
            print(f"   Collect Error {inst_dir.name}: {e}")

    print(f"   Collected {count} solutions to {local_save_dir}")
    print(f"   Pushed to {CVRPLIB_RECEIVE_DIR}")


# ================= 5. 主入口 =================

def main():
    print(f"=== Guardian Started (Time Limit: {WARM_START_DAY}s) ===")

    # 1. 提取 (按照 Instance/Method/Rank 结构)
    task_1_extract()

    # 2. 筛选 (根据配置选择最佳解，放入 init_sols)
    task_2_init_workspace()

    # 3. 计算 (并发运行)
    task_3_run_parallel()

    # 4. 回收 (保存并回传)
    task_4_collect_and_push()

    print("=== Guardian Finished ===")


if __name__ == "__main__":
    os.chdir(WS_ROOT)
    main()