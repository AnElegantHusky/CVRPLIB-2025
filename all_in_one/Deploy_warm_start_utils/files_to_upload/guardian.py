import os
import time
import shutil
import subprocess
import sqlite3
import json
import ast
from pathlib import Path
from datetime import datetime
from multiprocessing import Pool

# 【核心修改】引入提取函数
try:
    from extract_survivor_history import extract_solutions, routes_to_sol_file
except ImportError:
    print("[Error] extract_survivor_history.py not found! Make sure it is in the same directory.")
    exit(1)

# ================= 1. 全局配置 =================

WS_ROOT = Path("/app/all_in_one/SISR")
WS_INIT_SOLS = WS_ROOT / "init_sols"
WS_LOG_BUFFER = WS_ROOT / "log_buffer"
WS_RESULT_DIR = WS_ROOT / "result_sols"

CVRPLIB_ROOT = Path("/cvrplib_link/")
CVRPLIB_DB_DIR = CVRPLIB_ROOT / "log_buffer"
CVRPLIB_EXT_POOL = CVRPLIB_ROOT / "ails2_ext_sols"
CVRPLIB_RECEIVE_DIR = CVRPLIB_ROOT.parent.parent / "warm_start_outer_sol"

WARM_START_DAY = 1
WORKER_SCRIPT = "main_for_all_warm_start.py"

# 指定要从 CVRPLIB DB 提取哪些算法
EXTRACT_ALGOS = ["ails2_1day", "sisr_cvrp", "global_best"]
FILTER_METHOD_PRIORITY = ["global_best", "ails2_1day", "sisr_cvrp"]
FILTER_CRITERIA = "best_score"


# ================= 2. 筛选模块 (保持不变) =================

class SolutionFilter:
    @staticmethod
    def get_sol_cost(file_path):
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
        inst_pool = pool_dir / instance_name
        if not inst_pool.exists(): return None

        # 1. 按优先级找
        for method in FILTER_METHOD_PRIORITY:
            method_dir = inst_pool / method
            if not method_dir.exists(): continue

            sol_files = list(method_dir.glob("*.sol"))
            if not sol_files: continue

            # 2. 选最好的解
            if FILTER_CRITERIA == "best_score":
                sol_files.sort(key=lambda x: SolutionFilter.get_sol_cost(x))
                return sol_files[0]  # Cost 最小
            else:
                # latest (按文件名 1.sol, 2.sol 数字越小越新)
                sol_files.sort(key=lambda x: int(x.stem))
                return sol_files[0]

        # 3. 兜底
        all_sols = list(inst_pool.glob("**/*.sol"))
        if all_sols:
            return all_sols[0]
        return None


# ================= 3. 任务流程 =================

def task_1_extract():
    print(f"Step 1: Extracting history (Function Call)...")

    # 【核心修改】直接调用函数
    count = extract_solutions(
        db_root_path=CVRPLIB_DB_DIR,
        output_root_path=CVRPLIB_EXT_POOL,
        target_algos=EXTRACT_ALGOS,
        top_k=5
    )
    print(f"   Extracted {count} instances to {CVRPLIB_EXT_POOL}")


def task_2_init_workspace():
    print(f"Step 2: Filtering & Initializing Workspace...")

    # 清理并重建 init_sols 目录
    if WS_INIT_SOLS.exists(): shutil.rmtree(WS_INIT_SOLS)
    WS_INIT_SOLS.mkdir(parents=True, exist_ok=True)

    # 遍历解池 (CVRPLIB_EXT_POOL 下是按实例名分文件夹的)
    for inst_dir in CVRPLIB_EXT_POOL.iterdir():
        if not inst_dir.is_dir(): continue

        # 筛选最佳解
        best_sol = SolutionFilter.select_best_for_instance(inst_dir.name, CVRPLIB_EXT_POOL)

        if best_sol:
            # 【修正】：直接保存为 init_sols/InstanceName.sol
            target_file = WS_INIT_SOLS / f"{inst_dir.name}.sol"

            # 复制并重命名
            shutil.copy(best_sol, target_file)
            # print(f"   -> Prepared: {target_file.name} (from {best_sol.parent.name})")

    print(f"   Initialized {len(list(WS_INIT_SOLS.glob('*.sol')))} instances.")


def run_worker_process(instance_name):
    cmd = [
        "python3", WORKER_SCRIPT,
        "--instance_name", instance_name,
        "--warm_start_day", str(WARM_START_DAY),
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return (instance_name, True)
    except:
        return (instance_name, False)


def task_3_run_parallel():
    if not WS_INIT_SOLS.exists(): return

    # 【修正】：从 .sol 文件名中获取实例名 (e.g. "XL-London.sol" -> "XL-London")
    instances = [f.stem for f in WS_INIT_SOLS.glob("*.sol")]

    print(f"Step 3: Running {len(instances)} instances parallel...")

    if not instances:
        print("   [Warn] No .sol files found in init_sols!")
        return

    with Pool() as p:
        # 并发运行
        results = p.map(run_worker_process, instances)

    success_cnt = sum(1 for r in results if r[1])
    print(f"   Finished. Success: {success_cnt}/{len(instances)}")


def task_4_collect_and_push():
    print("Step 4: Collecting & Pushing...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_save_dir = WS_RESULT_DIR / timestamp
    local_save_dir.mkdir(parents=True, exist_ok=True)
    CVRPLIB_RECEIVE_DIR.mkdir(parents=True, exist_ok=True)

    for inst_dir in WS_LOG_BUFFER.iterdir():
        if not inst_dir.is_dir(): continue
        db_path = inst_dir / "shared.db"
        if not db_path.exists(): continue

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            row = conn.execute("SELECT solution, score FROM global_best WHERE id=1").fetchone()
            conn.close()

            if row:
                # 解析
                try:
                    routes = json.loads(row[0])
                except:
                    routes = ast.literal_eval(row[0])

                score = row[1]
                file_name = f"{inst_dir.name}.sol"

                # 【复用】使用 extract_survivor_history 里的写文件函数
                # 这样保证输出格式永远一致
                local_path = local_save_dir / file_name
                routes_to_sol_file(routes, score, local_path)

                shutil.copy(local_path, CVRPLIB_RECEIVE_DIR / file_name)
        except Exception as e:
            print(f"Error {inst_dir.name}: {e}")


# ================= 主入口 =================

if __name__ == "__main__":
    os.chdir(WS_ROOT)
    task_1_extract()
    task_2_init_workspace()
    task_3_run_parallel()
    task_4_collect_and_push()