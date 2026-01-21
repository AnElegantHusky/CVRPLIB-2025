import os
import time
import shutil
import subprocess
import sqlite3
import json
import ast
from pathlib import Path
import random
from datetime import datetime, timedelta, timezone
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
CVRPLIB_RECEIVE_DIR = CVRPLIB_ROOT / "warm_start_outer_sol"

WARM_START_DAY = 1
WORKER_SCRIPT = "main_for_all_warm_start.py"

# 指定要从 CVRPLIB DB 提取哪些算法
EXTRACT_ALGOS = [
            "ails2_etaMax1.000_stoppingTime86400.00",        # 1 天
            "ails2_etaMax1.000_stoppingTime432000.00",       # 5 天
            "ails2_etaMax1.000_stoppingTime864000.00",       # 10 天
            "ails2_etaMax1.000_stoppingTime1728000.00",      # 20 天
]
FILTER_METHOD_PRIORITY = [
            "ails2_etaMax1.000_stoppingTime1728000.00",      # 20 天
            "ails2_etaMax1.000_stoppingTime864000.00",       # 10 天
            "ails2_etaMax1.000_stoppingTime432000.00",       # 5 天
            "ails2_etaMax1.000_stoppingTime86400.00",        # 1 天
]
FILTER_CRITERIA = "best_score"


# ================= 2. 筛选模块 (保持不变) =================

# class SolutionFilter:
#     @staticmethod
#     def get_sol_cost(file_path):
#         try:
#             with open(file_path, 'r') as f:
#                 lines = f.readlines()
#                 for line in reversed(lines):
#                     if line.strip().startswith("Cost"):
#                         return float(line.strip().split()[-1])
#         except:
#             pass
#         return float('inf')
#
#     @staticmethod
#     def select_best_for_instance(instance_name, pool_dir):
#         inst_pool = pool_dir / instance_name
#         if not inst_pool.exists(): return None
#
#         # 1. 按优先级找
#         for method in FILTER_METHOD_PRIORITY:
#             method_dir = inst_pool / method
#             if not method_dir.exists(): continue
#
#             sol_files = list(method_dir.glob("*.sol"))
#             if not sol_files: continue
#
#             # 2. 选最好的解
#             if FILTER_CRITERIA == "best_score":
#                 sol_files.sort(key=lambda x: SolutionFilter.get_sol_cost(x))
#                 return sol_files[0]  # Cost 最小
#             else:
#                 # latest (按文件名 1.sol, 2.sol 数字越小越新)
#                 sol_files.sort(key=lambda x: int(x.stem))
#                 return sol_files[0]
#
#         # 3. 兜底
#         all_sols = list(inst_pool.glob("**/*.sol"))
#         if all_sols:
#             return all_sols[0]
#         return None

class SolutionFilter:
    # === 配置区域 ===
    # 算法启动时间：2026-01-12 23:30 (UTC+8 香港时间)
    START_DT = datetime(2026, 1, 12, 23, 30, tzinfo=timezone(timedelta(hours=8)))

    # 定义 (时长秒数, 文件夹名称) 的对应关系
    # 注意：这里按时长从大到小排列，方便后续逻辑
    METHOD_CONFIGS = [
        (1728000, "ails2_etaMax1.000_stoppingTime1728000.00"),  # 20 天
        (864000, "ails2_etaMax1.000_stoppingTime864000.00"),  # 10 天
        (432000, "ails2_etaMax1.000_stoppingTime432000.00"),  # 5 天
        (86400, "ails2_etaMax1.000_stoppingTime86400.00"),  # 1 天
    ]

    @staticmethod
    def get_sol_cost(file_path):
        """读取 sol 文件中的 Cost"""
        try:
            with open(file_path, 'r') as f:
                # 倒序读取，通常 Cost 在最后
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
        if not inst_pool.exists():
            return None

        # 1. 计算当前耗时 (elapsed seconds)
        now = datetime.now(timezone(timedelta(hours=8)))  # 当前香港时间
        elapsed_sec = (now - SolutionFilter.START_DT).total_seconds()

        target_folder_name = None

        # 2. 动态筛选：找“已结束”且“耗时最长”的方法
        # METHOD_CONFIGS 已经按时长降序排列
        for duration, folder_name in SolutionFilter.METHOD_CONFIGS:
            # 如果当前时间已经超过了该方法的停止时间
            if elapsed_sec >= duration:
                # 检查物理文件夹是否存在
                method_dir = inst_pool / folder_name
                if method_dir.exists():
                    # 找到了！这就是理论上完成的最长任务
                    target_folder_name = folder_name
                    break

        # 3. 兜底逻辑：如果没有任何一个满足时间条件（比如刚跑了半天），
        # 或者满足时间的文件夹不存在，则回退到找“存在的时长最短的那个”作为保底
        if target_folder_name is None:
            # 反向遍历（从短到长），找一个存在的
            for _, folder_name in reversed(SolutionFilter.METHOD_CONFIGS):
                if (inst_pool / folder_name).exists():
                    target_folder_name = folder_name
                    break

        if target_folder_name is None:
            return None

        # 4. 获取解并排序
        method_dir = inst_pool / target_folder_name
        sol_files = list(method_dir.glob("*.sol"))

        if not sol_files: return None

        # 按 Cost 排序 (Cost 越小越好)
        # 注意：这里必须读文件获取真实 Cost，而不是依赖文件名
        sol_files_with_cost = []
        for f in sol_files:
            c = SolutionFilter.get_sol_cost(f)
            if c != float('inf'):
                sol_files_with_cost.append((c, f))

        # 再次排序，确保是 Cost 升序
        sol_files_with_cost.sort(key=lambda x: x[0])

        if not sol_files_with_cost: return None

        # 5. Top-K 随机选择 (Top 10)
        # 取前 10 个最好的解
        top_k = sol_files_with_cost[:10]

        # 随机选一个。
        # 解释：随机性在 Warm Start 中很重要，能避免所有子进程都从完全相同的起点开始搜索，
        # 从而增加搜索空间的多样性。
        selected_pair = random.choice(top_k)

        # 打印日志方便调试（可选）
        # print(f"[{instance_name}] Time elapsed: {elapsed_sec/3600:.1f}h. "
        #       f"Selected from {target_folder_name} (Top {len(top_k)}). "
        #       f"Cost: {selected_pair[0]}")

        return selected_pair[1]  # 返回 Path 对象

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
    """
    运行单个实例的任务，并捕获输出以便调试
    """
    cmd = [
        "python3", WORKER_SCRIPT,
        "--instance_name", instance_name,
        "--warm_start_day", str(WARM_START_DAY),
        "--seed", "1"
    ]

    # 设置硬超时时间，比内部逻辑多给 30 秒缓冲，防止僵死
    HARD_TIMEOUT = WARM_START_DAY * 3600 * 24 + 3600
    # HARD_TIMEOUT = WARM_START_DAY * 3600 * 24 + 3600


    try:
        # capture_output=True 会同时捕获 stdout 和 stderr
        # text=True 让输出变为字符串
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            # timeout=HARD_TIMEOUT
        )
        # 如果成功，返回 True
        return (instance_name, True, None)

    except subprocess.CalledProcessError as e:
        # 脚本运行出错 (Return Code != 0)
        error_msg = (
            f"\n❌ [Error] Instance: {instance_name}\n"
            f"   Exit Code: {e.returncode}\n"
            f"   Command: {' '.join(cmd)}\n"
            f"   Error Output (Last 10 lines):\n"
            f"{'=' * 40}\n"
            f"{''.join(e.stderr.splitlines(keepends=True)[-10:])}"  # 只打最后10行，避免刷屏
            f"{'=' * 40}\n"
        )
        # 直接打印出来，或者返回给主进程
        print(error_msg)
        return (instance_name, False, error_msg)

    except subprocess.TimeoutExpired as e:
        # 脚本超时被强杀
        print(f"⏰ [Timeout] Instance {instance_name} exceeded {HARD_TIMEOUT}s.")
        return (instance_name, False, "Timeout")

    except Exception as e:
        # 其他 Python 调用错误
        print(f"⚠️ [Exception] Instance {instance_name}: {e}")
        return (instance_name, False, str(e))


def task_3_run_parallel():
    if not WS_INIT_SOLS.exists(): return

    # 获取所有任务名 (文件名去掉后缀)
    instances = [f.stem for f in WS_INIT_SOLS.glob("*.sol")]

    print(f"Step 3: Running {len(instances)} instances in parallel...")
    print(f"        (Hard Timeout set to {WARM_START_DAY}s)")

    if not instances:
        print("   [Warn] No .sol files found to run!")
        return

    start_t = time.time()

    # 使用 Pool 运行
    # processes=None 默认使用所有 CPU 核
    with Pool() as p:
        # map 会阻塞直到所有任务完成
        results = p.map(run_worker_process, instances)

    duration = time.time() - start_t

    # 统计结果
    success_cnt = sum(1 for r in results if r[1])
    fail_cnt = len(instances) - success_cnt

    print(f"\nStep 3 Finished in {duration:.1f}s.")
    print(f"   ✅ Success: {success_cnt}")
    print(f"   ❌ Failed:  {fail_cnt}")

    # 如果有失败，可以汇总打印一下失败的实例名
    if fail_cnt > 0:
        failed_instances = [r[0] for r in results if not r[1]]
        print(f"   Failed Instances: {failed_instances}")


def task_4_collect_and_push():
    print("Step 4: Collecting & Pushing (Atomic Mode)...")

    # 1. 准备目录
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    local_save_dir = WS_RESULT_DIR / timestamp
    local_save_dir.mkdir(parents=True, exist_ok=True)

    # 确保接收目录存在，并尝试给予目录本身 777 权限
    if not CVRPLIB_RECEIVE_DIR.exists():
        CVRPLIB_RECEIVE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(CVRPLIB_RECEIVE_DIR, 0o777)
    except Exception as e:
        # 只要能写进去就行，修改目录权限失败可以忽略
        pass

    count = 0
    # 2. 遍历结果
    for inst_dir in WS_LOG_BUFFER.iterdir():
        if not inst_dir.is_dir(): continue
        db_path = inst_dir / "shared.db"
        if not db_path.exists(): continue

        try:
            # 只读模式读取 DB
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            # 增加 SQL 执行超时防止死锁
            row = conn.execute("SELECT solution, score FROM global_best WHERE id=1").fetchone()
            conn.close()

            if row:
                sol_raw, score = row
                try:
                    routes = json.loads(sol_raw)
                except:
                    try:
                        routes = ast.literal_eval(sol_raw)
                    except:
                        print(f"   [Error] Failed to parse solution for {inst_dir.name}")
                        continue

                file_name = f"{inst_dir.name}.sol"

                # -------------------------------------------------
                # 动作 A: 先在本地归档 (Local Archive)
                # -------------------------------------------------
                local_path = local_save_dir / file_name
                routes_to_sol_file(routes, score, local_path)

                # 顺便把本地存档也改成 666，方便以后手动查看（可选）
                try:
                    os.chmod(local_path, 0o666)
                except:
                    pass

                # -------------------------------------------------
                # 动作 B: 原子化推送到共享目录 (Atomic Push)
                # -------------------------------------------------
                # 这里的逻辑是为了应对“接收方可能随时在读取”的情况

                final_target_path = CVRPLIB_RECEIVE_DIR / file_name
                temp_target_path = CVRPLIB_RECEIVE_DIR / f"{file_name}.tmp"

                # 1. Copy 到同一个目录下的临时文件 (.tmp)
                #    注意：必须先 copy 成 .tmp，此时接收方会忽略这个后缀的文件
                shutil.copy(local_path, temp_target_path)

                # 2. 修改临时文件的权限为 666 (rw-rw-rw-)
                #    这是最关键的一步，确保接收方容器（可能是非root用户）能删除它
                try:
                    os.chmod(temp_target_path, 0o666)
                except Exception as e:
                    print(f"   [Warn] Chmod failed on temp file: {e}")

                # 3. 原子重命名 (Atomic Rename)
                #    Linux 系统下，在同目录内 rename 是瞬间完成的。
                #    接收方永远不会读到“写了一半”的文件。
                os.replace(temp_target_path, final_target_path)

                count += 1

        except Exception as e:
            print(f"Error processing {inst_dir.name}: {e}")

    print(f"   ✅ Collected {count} solutions to {local_save_dir}")
    print(f"   ✅ Pushed safely to {CVRPLIB_RECEIVE_DIR}")

# ================= 主入口 =================

if __name__ == "__main__":
    for i in range(30):
        os.chdir(WS_ROOT)
        task_1_extract()
        task_2_init_workspace()
        task_3_run_parallel()
        task_4_collect_and_push()