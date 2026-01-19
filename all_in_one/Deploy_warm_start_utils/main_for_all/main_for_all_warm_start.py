import os
import subprocess
import sys
import numpy as np
import time
import ast
import multiprocessing
import traceback
import signal
import gc
import vrplib
import json
import psutil
import sqlite3
from pathlib import Path
import argparse
import glob
from write_outer_sol import save_best


from sisr2_db import sisr_cvrp

# ================= 配置与常量 =================
SISR_PATH = Path(__file__).resolve().parent
ROOT_PATH = SISR_PATH.parent
EXTERNAL_SOL_DIR_NAME = "ails2_ext_sols"

# Java Classpath 处理...
# classpath
# javac -cp "libs/*" -d target/classes src/Auxiliary/*.java src/Data/*.java src/DiversityControl/*.java src/Evaluators/*.java src/Improvement/*.java src/Perturbation/*.java src/SearchMethod/*.java src/Solution/*.java

# jar
# 1. javac -cp "libs/*" -d target/classes $(find src -name "*.java")
# mkdir -p target/classes/META-INF
# # 进入classes目录
# cd target/classes
# # 创建MANIFEST.MF
# # 写入正确的 MANIFEST.MF（注意替换主类路径）
# echo "Manifest-Version: 1.0" > META-INF/MANIFEST.MF
# echo "Main-Class: SearchMethod.AILSII" >> META-INF/MANIFEST.MF
# # 最后添加一个空行（必须）
# echo "" >> target/classes/META-INF/MANIFEST.MF
# cd ../..
# 打包classes目录下的所有文件（包括META-INF）到target/AILS2.jar
# jar -cvfm target/AILS2.jar target/classes/META-INF/MANIFEST.MF -C target/classes .


# 2. mvn clean package

java_cp_list = [
    ROOT_PATH / 'AILS2' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp = os.pathsep.join(str(p) for p in java_cp_list)

java_cp_eoh_acc_list = [
    ROOT_PATH / 'AILS2_Eoh_Acc' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',      # 

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_acc = os.pathsep.join(str(p) for p in java_cp_eoh_acc_list)         #   zkf 更改庆隆原先的问题


java_cp_eoh_acc_large_list = [
    ROOT_PATH / 'AILS2_Eoh_Acc_large' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',      # 

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_acc_large = os.pathsep.join(str(p) for p in java_cp_eoh_acc_large_list)         #   zkf 更改庆隆原先的问题

java_cp_eoh_ruin_list = [
    ROOT_PATH / 'AILS2_Eoh_Ruin' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',      # 

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_ruin = os.pathsep.join(str(p) for p in java_cp_eoh_ruin_list)


java_cp_eoh_omega_list = [
    ROOT_PATH / 'AILS2_Eoh_Omega' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',    #这里需要现场编译

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_omega = os.pathsep.join(str(p) for p in java_cp_eoh_omega_list)


java_cp_eoh_omega2_list = [
    ROOT_PATH / 'AILS2_Eoh_Omega2' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',    #这里需要现场编译

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_omega2 = os.pathsep.join(str(p) for p in java_cp_eoh_omega2_list)




java_cp_eoh_omega_acc_list = [
    ROOT_PATH / 'AILS2_Eoh_Omega_Acc' / 'target' / 'AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar',    #这里需要现场编译

    # ROOT_PATH / 'AILS2' / 'target' / 'classes',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-csv-1.10.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.10.2.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'junit-jupiter-api-5.14.0.jar',
    # ROOT_PATH / 'AILS2' / 'libs' / 'commons-io-2.15.1.jar',
]

java_cp_eoh_omega_acc = os.pathsep.join(str(p) for p in java_cp_eoh_omega_acc_list)




ails_main = "SearchMethod.AILSII"

# Java/C++ 路径配置 (建议放入配置文件或环境变量)
AILS2_PATH = ROOT_PATH / 'AILS2'

AILS2_EoH_ACC_PATH = ROOT_PATH / 'AILS2_Eoh_Acc'        #  1 增加新方法目录
AILS2_EoH_ACC_large_PATH = ROOT_PATH / 'AILS2_Eoh_Acc_large'        #  1 增加新方法目录
AILS2_EoH_Ruin_PATH = ROOT_PATH / 'AILS2_Eoh_Ruin'        #  1 增加新方法目录
AILS2_EoH_OMEGA_PATH = ROOT_PATH / 'AILS2_Eoh_Omega'    # zkf: 添加替换eoh设计的omega方法目录
AILS2_EoH_OMEGA2_PATH = ROOT_PATH / 'AILS2_Eoh_Omega2'    # zkf: 添加替换eoh设计的omega方法目录
AILS2_EoH_OMEGA_ACC_PATH = ROOT_PATH / 'AILS2_Eoh_Omega_Acc'    # zkf: 添加替换eoh设计的omega和acc方法目录

FILO2_PATH = ROOT_PATH / 'FILO2' / 'build'
# FILO2_PATH = ROOT_PATH / 'FILO2' / 'cmake-build-debug' # 

# HGS-TV C++ 路径（根据你的实际构建目录调整）
HGS_TV_PATH = ROOT_PATH / 'HGS-TV' / 'build'


# ================= 数据库管理类 (DB Handler) =================

class SharedDB:
    def __init__(self, db_path):
        self.db_path = str(db_path)

    def get_connection(self):
        """获取连接，设置超时防止 Locked"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)  # 30秒超时
        conn.row_factory = sqlite3.Row
        return conn

    def init_db(self):

        if os.path.exists(self.db_path):
            try:
                os.remove(self.db_path)
                # WAL 模式会生成 -wal 和 -shm 文件，也需要一并清除
                if os.path.exists(self.db_path + "-wal"): os.remove(self.db_path + "-wal")
                if os.path.exists(self.db_path + "-shm"): os.remove(self.db_path + "-shm")
                # print(f"[DB Init] Cleared existing database: {self.db_path}")
            except OSError as e:
                print(f"[DB Init Warning] Failed to delete old DB: {e}")

        with self.get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL;")  # 关键：开启 WAL 支持并发读写
            conn.execute("PRAGMA busy_timeout = 30000;")

            conn.execute("""
                         CREATE TABLE IF NOT EXISTS global_best (
                             id INTEGER PRIMARY KEY CHECK ( id = 1 ),
                             score REAL,
                             solution TEXT,
                             algo_name TEXT,
                             runningtime REAL
                             );
                         """)

            conn.execute(
                "INSERT OR IGNORE INTO global_best (id, score, solution, algo_name, runningtime) VALUES (1, 1e20, '', '', 0)")

            conn.execute("""
                         CREATE TABLE IF NOT EXISTS solution_history(
                             id INTEGER PRIMARY KEY AUTOINCREMENT,
                             algo_name TEXT,
                             score REAL,
                             solution TEXT,
                             runningtime REAL
                         );
                         """)

            conn.execute("CREATE INDEX IF NOT EXISTS idx_algo_time ON solution_history (algo_name, runningtime);")

            conn.execute("""
                         CREATE TABLE IF NOT EXISTS survivor_stats
                         (
                             algo_name TEXT PRIMARY KEY,
                             seed_count INTEGER DEFAULT 0
                         );
                         """)

            conn.execute("""
                         CREATE TABLE IF NOT EXISTS improvement_stats
                         (
                             id INTEGER PRIMARY KEY AUTOINCREMENT,
                             seed_algo TEXT, 
                             seed_score REAL, 
                             winner_algo TEXT, 
                             winner_score REAL, 
                             improvement REAL, 
                             recording_time REAL  
                         );
                         """)

            conn.execute("""
                        INSERT OR IGNORE INTO global_best (id, score, solution, algo_name, runningtime)
                        VALUES (1, 1e20, '[]', 'init_placeholder', 0)
                    """)

            conn.commit()

    # =================== 2. 新增 注入函数 ===================
    def inject_initial_solution(instance_name, db_path):
        """
        从 ails2_ext_sols 读取解并注入 DB
        """
        # 构造寻找路径: ROOT/ails2_ext_sols/InstanceName/**/*.sol
        # 使用 glob 递归查找，因为中间层可能是 {fixed_method_name}
        search_pattern = ROOT_PATH / EXTERNAL_SOL_DIR_NAME / instance_name / "**" / "*.sol"

        found_files = glob.glob(str(search_pattern), recursive=True)

        if not found_files:
            print(f"[Init Injector] ⚠️ No initial solution found in {search_pattern}")
            return

        # 默认取第一个找到的 sol 文件
        sol_file = Path(found_files[0])
        print(f"[Init Injector] 🎯 Loading initial solution: {sol_file.name}")

        try:
            # 使用 vrplib 读取
            solution_data = vrplib.read_solution(str(sol_file))

            # 解析 Routes
            routes = solution_data.get('routes')
            if not routes:
                print("[Init Injector] ❌ Error: 'routes' not found in solution file.")
                return

            # 获取 Score (Cost)
            # VRPLIB 格式通常在 Header 里有 Cost，或者 solution_data['cost']
            # 如果没有，我们需要一个备用计算器，或者信任文件名/目录名？
            # 这里假设 vrplib.read_solution 能解析出 cost
            score = solution_data.get('cost')

            if score is None:
                # 尝试从 Edge Weight 字段读取，或者如果这里有 distance matrix 可以计算
                # 为简单起见，如果读不到 Cost，暂时设为一个较大的数或报错
                # 或者尝试从文件名读取 (例如: XL-London_12345.sol)
                print("[Init Injector] ⚠️ Cost not found in .sol file metadata. Using 1e10 (Dangerous!)")
                score = 1e10

                # 调用 write_outer_sol 的 save_best
            # 注意：save_best 内部执行的是 UPDATE ... WHERE score > new_score
            # 因为我们在 init_db 里插入了 1e20，所以这里一定会更新成功
            success = save_best(db_path, 0, float(score), routes, "Inject_Warm_Start")

            if success:
                print(f"[Init Injector] ✅ Successfully injected init sol (Score: {score})")
            else:
                print("[Init Injector] ❌ Injection failed (DB Locked or Logic Error).")

        except Exception as e:
            print(f"[Init Injector] 💥 Exception during injection: {e}")
            traceback.print_exc()

    def get_status(self):
        """获取当前面板状态（用于监控）"""
        global_best_info = None
        with self.get_connection() as conn:
            # 获取全局最优
            row = conn.execute("SELECT score, algo_name, runningtime, solution FROM global_best WHERE id=1").fetchone()
            global_best_info = dict(row) if row else None
        return global_best_info

    def log_survivor(self, algo_name):
        """记录哪个算法提供了用于重置的初始解"""
        if not algo_name: return
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO survivor_stats (algo_name, seed_count) 
                VALUES (?, 1) 
                ON CONFLICT(algo_name) DO UPDATE SET seed_count = seed_count + 1
            """, (algo_name,))
            conn.commit()

    def log_improvement(self, seed_algo, seed_score, winner_algo, winner_score, recording_time):
        """记录一次优化事件：谁基于谁的解提升了多少"""
        improvement = seed_score - winner_score
        # 如果是无穷大（第一次找到解），提升值记为 0 或者特定标记
        if seed_score > 1e19:
            improvement = 0.0

        with self.get_connection() as conn:
            conn.execute("""
                         INSERT INTO improvement_stats (seed_algo, seed_score, winner_algo, winner_score, improvement, recording_time)
                         VALUES (?, ?, ?, ?, ?, ?)
                         """, (seed_algo, seed_score, winner_algo, winner_score, improvement, recording_time))
            conn.commit()

    def print_stats(self):
        """打印最终统计结果"""
        with self.get_connection() as conn:
            rows = conn.execute("SELECT algo_name, count FROM best_stats ORDER BY count DESC").fetchall()
            print("\n" + "="*20 + " Final Statistics " + "="*20)
            print(f"{'Algorithm Name':<30} | {'Best Solution Updates':<10}")
            print("-" * 45)
            for row in rows:
                print(f"{row['algo_name']:<30} | {row['count']:<10}")
            print("="*45 + "\n")

# ================= 辅助函数 =================

def smart_decode(byte_data):
    if not byte_data: return ""
    try:
        return byte_data.decode('utf-8')
    except:
        return byte_data.decode('latin-1', errors='replace')

# ================= Worker 封装 =================

def run_sisr(data, vehicle_capcity, file, shared_db, start_time, max_running_time_min, update_interval):
    sisr_cvrp(
        data, vehicle_capcity,
        inst_name=file,
        shared_db=shared_db,
        start_time=start_time,
        update_interval=update_interval,
        n_iter=4_00000,  # 4_000
        max_running_time=max_running_time_min / 60,  # hour
        # max_running_time = 1/3600, # hour
        init_T=100.0,
        final_T=1.0,
        n_iter_fleet=None,
        fleet_gap=100,
        obj_n_routes=20,
        verbose_step=None,
        time_window=False,
        soft_time_window=False
    )


def kill_process_tree(pid):
    """
    递归杀死进程树：先杀子进程（Java/C++），再杀父进程（Python Wrapper）
    """
    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)  # 获取所有孙子/子进程

        # 先杀死所有子进程 (Java/C++)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass

        # 等待子进程结束
        _, alive = psutil.wait_procs(children, timeout=1)
        for p in alive:
            p.kill()  # 强制杀死

        # 杀死父进程 (Python Wrapper)
        parent.terminate()
        parent.wait(1)

    except psutil.NoSuchProcess:
        pass

def run_external_process(cmd):
    """通用的外部进程运行器"""
    # print(cmd)
    print(' '.join(cmd))
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        if stderr:
            print(f"[Error] {' '.join(cmd[:2])}: {smart_decode(stderr)}")
    except Exception as e:
        print(f"[Exception] Failed to run {cmd[0]}: {e}")


def update_cmd_arg(base_cmd, flag, value):
    """通用的参数替换函数，替代 index 查找"""
    cmd = base_cmd.copy()
    try:
        idx = cmd.index(flag)
        cmd[idx + 1] = str(value)
    except ValueError:
        pass
    return cmd

# ================= 核心管理逻辑 =================
finished_external = []

def manage_workers(process_dict,
                   sisr_args,
                   ails_common_args,
                   ails_configs,
                   filo_template,
                   hgs_template,
                   ails_eoh_acc_template,
                   ails_eoh_omega_template,
                   ails_eoh_omega2_template,
                   ails_eoh_omega_acc_template,
                   best_info,
                   start_time,
                   ails_eoh_acc_large_template=None,
                   ails_eoh_ruin_template=None):  # add new template
    """
    智能管理进程重启。
    process_dict: {'sisr': proc, 'ails': proc, ...}
    best_info: {'algo': 'algo_name', 'sol': [...], 'dist': 123.4}
    """

    survivor_name_list = [
        # best_info.get('algo_name'),
        # 'AILS2_1day',
        # 'AILS2_5day',
        # 'AILS2_10day',
        # 'AILS2_15day',
        # 'ails2_eoh_acc_large',
        'AILS2_etaMax001_limit5d',
        'ails2_eoh_omega2'
    ]

    # 1. 终止非幸存者进程
    for name, p in list(process_dict.items()):
        if p and p.is_alive():
            if name in survivor_name_list:
                continue
            kill_process_tree(p.pid)
            p.join(timeout=1)
            del process_dict[name]

    # 1.5 如果 AILS2_1day/5day/10day/20day已经跑完，则终止对应进程
    # for name in ['AILS2_1day', 'AILS2_5day', 'AILS2_10day', 'AILS2_15day']:
    #     if name not in process_dict:
    #         continue
    #     p = process_dict[name]
    #     if not p.is_alive():
    #         kill_process_tree(p.pid)
    #         p.join(timeout=1)
    #         del process_dict[name]
    #         finished_external.append(name)


    # 2. 垃圾回收 (关键：防止内存泄漏)
    gc.collect()

    # # 3. 重启被终止的进程
    # # --- AILS2 (Java) ---
    # if not process_dict.get('ails2') or not process_dict['ails2'].is_alive():
    #     cmd = update_cmd_arg(ails_template, "-crtRunningTime", time.time() - start_time)
    #     p = multiprocessing.Process(
    #         target=run_external_process,
    #         args=(ails_template,),
    #         name="ails2"
    #     )
    #     p.start()
    #     process_dict['ails2'] = p

    # 2. 重启/启动 AILS2 多实例

    for config in ails_configs:     # ails_configs: AILS2_1day, AILS2_5day, AILS2_10day, AILS2_15day,
                                    # AILS2_etaMax0005_limit24h, AILS2_etaMax002_limit24h, AILS2_etaMax001_limit5d
        unique_name = config['name']
        if unique_name in finished_external:
            continue

        # 只有当该进程不存在或已死时才启动
        if not process_dict.get(unique_name) or not process_dict[unique_name].is_alive():
            # 构建该特定配置的命令
            cmd = list(ails_common_args)  # 复制通用部分

            # 添加/覆盖特定参数
            cmd.extend(["-etaMax", str(config['etaMax'])])
            cmd.extend(["-limit", str(config['limit'])])
            cmd.extend(["-crtRunningTime", str(time.time() - start_time)])

            p = multiprocessing.Process(
                target=run_external_process,
                args=(cmd,),
                name=unique_name
            )
            p.start()
            process_dict[unique_name] = p

    # if not process_dict.get('ails2_eoh_acc') or not process_dict['ails2_eoh_acc'].is_alive():       # :
    #     # 构建该特定配置的命令
    #     p = multiprocessing.Process(
    #         target=run_external_process,
    #         args=(ails_eoh_acc_template,),
    #         name='ails2_eoh_acc'
    #     )
    #     p.start()
    #     process_dict['ails2_eoh_acc'] = p
    #
    # if ails_eoh_acc_large_template:
    #     if not process_dict.get('ails2_eoh_acc_large') or not process_dict['ails2_eoh_acc_large'].is_alive():       # :
    #         # 构建该特定配置的命令
    #         p = multiprocessing.Process(
    #             target=run_external_process,
    #             args=(ails_eoh_acc_large_template,),
    #             name='ails2_eoh_acc_large'
    #         )
    #         p.start()
    #         process_dict['ails2_eoh_acc_large'] = p

    # if ails_eoh_ruin_template:
    #     if not process_dict.get('ails2_eoh_ruin') or not process_dict['ails2_eoh_ruin'].is_alive():       # :
    #         # 构建该特定配置的命令
    #         p = multiprocessing.Process(
    #             target=run_external_process,
    #             args=(ails_eoh_ruin_template,),
    #             name='ails2_eoh_ruin'
    #         )
    #         p.start()
    #         process_dict['ails2_eoh_ruin'] = p

    # if not process_dict.get('ails2_eoh_omega') or not process_dict['ails2_eoh_omega'].is_alive():       #add omega
    #     # 构建该特定配置的命令
    #     p = multiprocessing.Process(
    #         target=run_external_process,
    #         args=(ails_eoh_omega_template,),
    #         name='ails2_eoh_omega'
    #     )
    #     p.start()
    #     process_dict['ails2_eoh_omega'] = p

    if not process_dict.get('ails2_eoh_omega2') or not process_dict['ails2_eoh_omega2'].is_alive():       #add omega2
        # 构建该特定配置的命令
        p = multiprocessing.Process(
            target=run_external_process,
            args=(ails_eoh_omega2_template,),
            name='ails2_eoh_omega2'
        )
        p.start()
        process_dict['ails2_eoh_omega2'] = p

    # if not process_dict.get('ails2_eoh_omega_acc') or not process_dict['ails2_eoh_omega_acc'].is_alive():       #add omega and acc
    #     # 构建该特定配置的命令
    #     p = multiprocessing.Process(
    #         target=run_external_process,
    #         args=(ails_eoh_omega_acc_template,),
    #         name='ails2_eoh_omega_acc'
    #     )
    #     p.start()
    #     process_dict['ails2_eoh_omega_acc'] = p

    # --- FILO2 (C++) ---
    # if not process_dict.get('filo2') or not process_dict['filo2'].is_alive():
    #     p = multiprocessing.Process(
    #         target=run_external_process,
    #         args=(filo_template,),
    #         name="filo2"
    #     )
    #     p.start()
    #     process_dict['filo2'] = p
    #
    # # --- HGS-TV (C++) ---
    # if hgs_template is not None:
    #     if not process_dict.get('HGS-TV') or not process_dict['HGS-TV'].is_alive():
    #         p = multiprocessing.Process(
    #             target=run_external_process,
    #             args=(hgs_template,),
    #             name="HGS-TV"
    #         )
    #         p.start()
    #         process_dict['HGS-TV'] = p

    # --- SISR ---
    # if not process_dict.get('sisr') or not process_dict['sisr'].is_alive():
    #     # 更新参数（这里需要根据你的实际 sisr 函数签名调整）
    #     p = multiprocessing.Process(
    #         target=run_sisr,
    #         args=(*sisr_args,),
    #         name="sisr"
    #     )
    #     p.start()
    #     process_dict['sisr'] = p

def inject_initial_solution(instance_name, db_path):
    """
    从 ails2_ext_sols 读取解并注入 DB
    """
    # 构造寻找路径: ROOT/ails2_ext_sols/InstanceName/**/*.sol
    # 使用 glob 递归查找，因为中间层可能是 {fixed_method_name}
    search_pattern = ROOT_PATH / EXTERNAL_SOL_DIR_NAME / instance_name / "**" / "*.sol"

    found_files = glob.glob(str(search_pattern), recursive=True)

    if not found_files:
        print(f"[Init Injector] ⚠️ No initial solution found in {search_pattern}")
        return

    # 默认取第一个找到的 sol 文件
    sol_file = Path(found_files[0])
    print(f"[Init Injector] 🎯 Loading initial solution: {sol_file.name}")

    try:
        # 使用 vrplib 读取
        solution_data = vrplib.read_solution(str(sol_file))

        # 解析 Routes
        routes = solution_data.get('routes')
        if not routes:
            print("[Init Injector] ❌ Error: 'routes' not found in solution file.")
            return

        # 获取 Score (Cost)
        # VRPLIB 格式通常在 Header 里有 Cost，或者 solution_data['cost']
        # 如果没有，我们需要一个备用计算器，或者信任文件名/目录名？
        # 这里假设 vrplib.read_solution 能解析出 cost
        score = solution_data.get('cost')

        if score is None:
            # 尝试从 Edge Weight 字段读取，或者如果这里有 distance matrix 可以计算
            # 为简单起见，如果读不到 Cost，暂时设为一个较大的数或报错
            # 或者尝试从文件名读取 (例如: XL-London_12345.sol)
            print("[Init Injector] ⚠️ Cost not found in .sol file metadata. Using 1e10 (Dangerous!)")
            score = 1e10

            # 调用 write_outer_sol 的 save_best
        # 注意：save_best 内部执行的是 UPDATE ... WHERE score > new_score
        # 因为我们在 init_db 里插入了 1e20，所以这里一定会更新成功
        success = save_best(db_path, 0, float(score), routes, "Inject_Warm_Start")

        if success:
            print(f"[Init Injector] ✅ Successfully injected init sol (Score: {score})")
        else:
            print("[Init Injector] ❌ Injection failed (DB Locked or Logic Error).")

    except Exception as e:
        print(f"[Init Injector] 💥 Exception during injection: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    multiprocessing.freeze_support()

    one_day_time_sec = 24 * 60 * 60
    dMax = 30
    dMin = 15
    gamma = 30
    varphi = 40
    crtRunningTime = 0.

    writing_interval_sec = 60

    # 1. 参数解析优化
    parser = argparse.ArgumentParser(description="Warm Start Worker Script")
    parser.add_argument("--instance_name", type=str, required=True, help="Instance Name (e.g., XL-London_1)")
    parser.add_argument("--seed", type=int, default=1, help="Random Seed")
    # 新增 warm_start_time 参数，由 Guardian 决定跑多久
    parser.add_argument("--warm_start_day", type=int, default=2, help="Running duration in seconds")

    args, unknown = parser.parse_known_args()

    instance_name = args.instance_name
    instance_path = ROOT_PATH / 'SISR' / 'data' / args.instances_path / f'{instance_name}.vrp' # TODO: check path

    seed = args.seed
    warm_start_day = args.warm_start_day  # 设定运行总时长

    # 路径定义
    db_dir = SISR_PATH / "log_buffer" / instance_name
    shared_db_path = db_dir / "shared.db"

    # --- Step 1: 环境清理 (Guardian可能做过，但这里再做一次保险) ---
    if shared_db_path.exists() and shared_db_path.is_file():
        try:
            shared_db_path.unlink()
            print(f"文件 {shared_db_path} 已删除。")
        except OSError as e:
            print(f"删除失败: {e}")
    else:
        print("文件不存在。")
    db_dir.mkdir(parents=True, exist_ok=True)

    # --- Step 2: 初始化 DB ---
    db_handler = SharedDB(shared_db_path)
    db_handler.init_db()

    # --- Step 3: 注入初解 (从外部目录) ---
    inject_initial_solution(instance_name, shared_db_path)

    # --- Step 4: 定义只运行的两个特定算法 ---
    # 基础命令模板 (根据你的实际 jar 包位置和参数调整)
    # 注意：这里假设 jar 包和 classpath 都在 ../AILS2 下，请根据实际 Docker 路径确认
    base_java_cmd = "java -cp \"../AILS2/libs/*:../AILS2/target/classes\" SearchMethod.AILSII"

    # 4.1 构造 ails2_etaMax_0.01 命令
    # 这里的参数根据你的原始代码逻辑提取

    start_time = time.time()

    ails_cmd = [
        "java",
        # "--enable-native-access=ALL-UNNAMED", # handle the warning
        "-jar", java_cp,
        "-file", instance_path.as_posix(),
        "-sharedDB", shared_db_path.as_posix(),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None",
        "-limit", str(warm_start_day * one_day_time_sec),  # second
        "-crtRunningTime", str(crtRunningTime),  # second
        "-stoppingCriterion", "Time",
        "-dMax", str(dMax),
        "-dMin", str(dMin),
        "-gamma", str(gamma),
        "-varphi", str(varphi),
        "-startTime", str(start_time),
        "-updateInterval", str(writing_interval_sec),
        # "-etaMax", str(etaMax),
    ]

    # 4.2 构造 eoh_omega2 命令 (假设这是 AILS 的另一种参数配置，或者是独立的 EOH jar)
    # 如果是同一个 jar 只是参数不同：
    ails_eoh_omega2_cmd = [  # : AILSII不同版本新增cmd
        "java",
        # "--enable-native-access=ALL-UNNAMED", # handle the warning
        "-jar", java_cp_eoh_omega2,
        "-file", instance_path.as_posix(),
        "-sharedDB", shared_db_path.as_posix(),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None",
        "-limit", str(warm_start_day * one_day_time_sec),  # second
        "-crtRunningTime", str(crtRunningTime),  # second
        "-stoppingCriterion", "Time",
        "-dMax", str(dMax),
        "-dMin", str(dMin),
        "-gamma", str(gamma),
        "-varphi", str(varphi),
        "-startTime", str(start_time),
        "-updateInterval", str(writing_interval_sec),
        "-etaMax", "0.01",
    ]

    # 如果 EOH 是完全不同的程序，请替换上面的 cmd_eoh_omega2 字符串

    workers = []

    # --- Step 5: 启动子进程 ---
    try:
        print(f"🔥 [WarmStart] Launching: ails2_etaMax_0.01")
        p1 = subprocess.Popen(ails_cmd, shell=True, start_new_session=True)
        workers.append(p1)

        print(f"🔥 [WarmStart] Launching: eoh_omega2")
        p2 = subprocess.Popen(ails_eoh_omega2_cmd, shell=True, start_new_session=True)
        workers.append(p2)

        # --- Step 6: 进入监控循环 (倒计时) ---
        # 复用 manage_workers 函数，或者直接写一个简单的等待循环
        # 这里建议直接调用 manage_workers，因为它包含了读 DB 更新 crt_best 的逻辑

        # 为了适配 manage_workers 的接口，我们需要传递那些 template 参数
        # 但既然我们只有两个固定进程，其实只需要监控时间即可


    except KeyboardInterrupt:
        print("\n🛑 [WarmStart] Interrupted by user.")
    finally:
        # --- Step 7: 清理退出 ---
        print("🧹 [WarmStart] Terminating workers...")
        for p in workers:
            kill_process_tree(p)

        print("✅ [WarmStart] Done.")
        sys.exit(0)