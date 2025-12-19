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


from sisr2_db import sisr_cvrp

# ================= 配置与常量 =================
SISR_PATH = Path(__file__).resolve().parent
ROOT_PATH = SISR_PATH.parent

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

ails_main = "SearchMethod.AILSII"

# Java/C++ 路径配置 (建议放入配置文件或环境变量)
AILS2_PATH = ROOT_PATH / 'AILS2'
# FILO2_PATH = ROOT_PATH / 'FILO2' / 'build'
FILO2_PATH = ROOT_PATH / 'FILO2' / 'cmake-build-debug' # TODO

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

            conn.commit()

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

def manage_workers(process_dict, sisr_args, ails_common_args, ails_configs, filo_template, hgs_template, best_info, start_time):
    """
    智能管理进程重启。
    process_dict: {'sisr': proc, 'ails': proc, ...}
    best_info: {'algo': 'algo_name', 'sol': [...], 'dist': 123.4}
    """

    survivor_name = best_info.get('algo_name')

    # 1. 终止非幸存者进程
    for name, p in list(process_dict.items()):
        if p and p.is_alive():
            if name == survivor_name:
                continue
            kill_process_tree(p.pid)
            p.join(timeout=1)
            del process_dict[name]

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
    for config in ails_configs:
        unique_name = config['name']

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

    # --- FILO2 (C++) ---
    if not process_dict.get('filo2') or not process_dict['filo2'].is_alive():
        p = multiprocessing.Process(
            target=run_external_process,
            args=(filo_template,),
            name="filo2"
        )
        p.start()
        process_dict['filo2'] = p

    # --- HGS-TV (C++) ---
    if hgs_template is not None:
        if not process_dict.get('HGS-TV') or not process_dict['HGS-TV'].is_alive():
            p = multiprocessing.Process(
                target=run_external_process,
                args=(hgs_template,),
                name="HGS-TV"
            )
            p.start()
            process_dict['HGS-TV'] = p

    # --- SISR ---
    if not process_dict.get('sisr') or not process_dict['sisr'].is_alive():
        # 更新参数（这里需要根据你的实际 sisr 函数签名调整）
        p = multiprocessing.Process(
            target=run_sisr,
            args=(*sisr_args,),
            name="sisr"
        )
        p.start()
        process_dict['sisr'] = p


# ================= 主程序入口 =================

if __name__ == '__main__':
    # python main_for_all3.py XLTEST-n1048-k139 20
    parser = argparse.ArgumentParser()
    parser.add_argument('instance_name', help='Instance name.')
    parser.add_argument('running_time_min', type=int, help='Max running time in minutes.')
    parser.add_argument('warmup_sec', type=int, help='Warmup time in seconds.')
    parser.add_argument('update_interval_sec', type=int, help='Update interval in seconds.')
    args = parser.parse_args()

    # 1. 强制 Spawn
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

    # 路径与数据初始化 (简化版)
    # instance_name = 'XLTEST-n3101-k685'
    # instance_name = 'XLTEST-n2168-k625'
    # instance_name = 'XLTEST-n1048-k139'
    # instance_name = 'XLTEST-n8575-k343'
    instance_name = args.instance_name

    # 使用 pathlib 拼接路径
    instance_path = ROOT_PATH / 'SISR' / 'data' / 'cvrplib_1019' / f'{instance_name}.vrp'

    vrp_data = vrplib.read_instance(str(instance_path))
    vehicle_capacity = vrp_data['capacity']
    data = np.concatenate((vrp_data['node_coord'], vrp_data['demand'][:, None]), axis=1)
    inst_size = data.shape[0]

    log_path = ROOT_PATH / 'SISR' / 'log_buffer' / instance_name
    log_path.mkdir(parents=True, exist_ok=True)

    crt_best_dist = float('inf')

    # Shared CSV
    # shared_csv = log_path / 'shared.csv'
    # shared_csv.write_text('', encoding='utf-8')

    shared_db_path = log_path / 'shared.db'
    db_handler = SharedDB(shared_db_path)
    db_handler.init_db()

    start_time = time.time()
    # max_running_time_min = inst_size // 25
    # max_running_time_min = 20  # TODO: ONLY FOR DEBUG
    max_running_time_min = args.running_time_min

    # 参数模版 (Template)
    # 将可变参数用占位符或在 build 函数中动态替换
    # limit = max_running_time_min * 60
    # limit_min = 5
    update_interval_sec = args.update_interval_sec
    warmup_sec = args.warmup_sec
    db_check_interval_sec = min(15, update_interval_sec/2)
    # etaMax = 1
    dMax = 30
    dMin = 15
    gamma = 30
    varphi = 40
    crtRunningTime = 0.

    # 1. 定义多种 AILS2 配置
    ails_configs = [
        {'name': f'AILS2_etaMax001_limit24h',   'etaMax': 0.01, 'limit': 24*60*60},
        {'name': 'AILS2_etaMax005_limit24h',   'etaMax': 0.05, 'limit': 24*60*60},
        {'name': 'AILS2_etaMax01_limit24h',   'etaMax': 0.1, 'limit': 24*60*60},
        {'name': 'AILS2_etaMax1_limit10min',   'etaMax': 1, 'limit': 10*60},
        {'name': 'AILS2_etaMax1_limit1h',   'etaMax': 1, 'limit': 1*60*60},
        {'name': 'AILS2_etaMax1_limit2h',   'etaMax': 1, 'limit': 2*60*60},
        {'name': 'AILS2_etaMax1_limit4h',   'etaMax': 1, 'limit': 4*60*60},
        {'name': 'AILS2_etaMax1_limit8h',   'etaMax': 1, 'limit': 8*60*60},
    ]

    # ails_cmd = [
    #     "java", "-classpath", java_cp, ails_main,  # 假设入口
    #     "-file", instance_path.as_posix(),
    #     "-sharedCSV", shared_csv.as_posix(),
    #     "-logPath", ails_log_path.as_posix(),
    #     "-rounded", "true",
    #     "-best", "0",
    #     "-initSolution", "None",
    #     "-limit", str(limit),  # second
    #     "-stoppingCriterion", "Time",
    #     "-dMax", str(dMax),
    #     "-dMin", str(dMin),
    #     "-gamma", str(gamma),
    #     "-varphi", str(varphi),
    #     "-startTime", str(start_time),
    # ]

    ails_cmd = [
        "java",
        # "--enable-native-access=ALL-UNNAMED", # handle the warning
        "-jar", java_cp,
        "-file", instance_path.as_posix(),
        "-sharedDB", shared_db_path.as_posix(),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None",
        # "-limit", str(limit_min * 60),  # second
        "-crtRunningTime", str(crtRunningTime),  # second
        "-stoppingCriterion", "Time",
        "-dMax", str(dMax),
        "-dMin", str(dMin),
        "-gamma", str(gamma),
        "-varphi", str(varphi),
        "-startTime", str(start_time),
        "-updateInterval", str(update_interval_sec),
        # "-etaMax", str(etaMax),
    ]

    filo_exe_name = "filo2.exe" if os.name == "nt" else "filo2"
    filo_exe = FILO2_PATH / filo_exe_name

    filo_cmd = [
        str(filo_exe),
        instance_path.as_posix(),
        "--shared-db", shared_db_path.as_posix(),
        "--start-time", str(start_time),
        "--max-running-seconds", str(max_running_time_min * 60),
        "--update-interval-seconds", str(update_interval_sec)
    ]

    # --- HGS-TV (C++) 命令 ---
    hgs_exe_name = "hgs.exe" if os.name == "nt" else "hgs"
    hgs_exe = HGS_TV_PATH / hgs_exe_name

    hgs_cmd = [
        str(hgs_exe),
        instance_path.as_posix(),
        "-sharedDB", shared_db_path.as_posix(),
        "-startTime", str(start_time),
        "-t", str(max_running_time_min * 60),
        "-type", "Uchoa",
        "-seed", "1",
        "-deco", "BarycentreClustering",
        "-updateInterval", str(update_interval_sec),
    ]

    sisr_args = [
        data,
        vehicle_capacity,
        instance_name,
        str(shared_db_path),
        start_time,
        max_running_time_min,
        update_interval_sec,
    ]

    # 进程字典
    # process_dict = {'ails2': None, 'filo2': None, 'sisr': None, 'HGS-TV': None}
    process_dict = {}

    # 初始启动：同时启动 AILS2 / FILO2 / SISR / HGS-TV
    manage_workers(process_dict, sisr_args, ails_cmd, ails_configs, filo_cmd, hgs_cmd, {}, start_time)
    time.sleep(warmup_sec) # warmup

    # 【优化2】文件监听循环
    try:
        while True:
            if time.time() - start_time > max_running_time_min * 60:
                break
            try:
                global_best_info = db_handler.get_status()
                if global_best_info and crt_best_dist > global_best_info['score']:
                    print(global_best_info['algo_name'], global_best_info['score'])
                    crt_best_dist = global_best_info['score']

                    db_handler.log_survivor(global_best_info['algo_name'])

                    manage_workers(process_dict, sisr_args, ails_cmd, ails_configs, filo_cmd, hgs_cmd, global_best_info, start_time)
            except Exception as e:
                # 4. 详细异常信息输出
                exc_type, exc_value, exc_traceback = sys.exc_info()  # 获取完整异常信息
                # 拼接详细报错信息
                error_detail = (
                    f"\n==================== 监控模块异常 ====================\n"
                    f"异常类型: {exc_type.__name__}\n"  # 异常类型（如KeyError/TypeError）
                    f"异常描述: {str(exc_value)}\n"  # 异常具体信息（如'key not found: score'）
                    f"当前crt_best_dist值: {crt_best_dist}\n"  # 上下文变量
                    f"当前global_best_info值: {global_best_info if 'global_best_info' in locals() else '未定义'}\n"  # 避免变量未定义报错
                    f"\n完整堆栈跟踪:\n{traceback.format_exc()}"  # 完整堆栈（定位到具体代码行）
                    f"=====================================================================\n"
                )
                # 打印详细报错（也可写入日志文件）
                print(f"[Monitor Error] {error_detail}")
            time.sleep(db_check_interval_sec)  # 轮询间隔，不要太频繁

    except KeyboardInterrupt:
        print("Stopping...")
    except Exception as e:
        traceback.print_exc()
    finally:
        for p in process_dict.values():
            if p and p.is_alive():
                kill_process_tree(p.pid)
                p.join()
        gc.collect()
        print("Done.")