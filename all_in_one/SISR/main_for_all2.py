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
from pathlib import Path


from sisr2 import sisr_cvrp

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
FILO2_PATH = ROOT_PATH / 'FILO2' / 'build'

# ================= 辅助函数 =================

def smart_decode(byte_data):
    if not byte_data: return ""
    try:
        return byte_data.decode('utf-8')
    except:
        return byte_data.decode('latin-1', errors='replace')


def parse_solution_line(line):
    """
    轻量级解析，替代 pd.read_csv。
    假设 CSV 格式为: algorithm_name, time, distance, solution_str
    """
    try:
        parts = line.strip().split(',')
        if len(parts) < 4: return None

        algo = parts[0]
        dist = float(parts[2])
        sol_str = ",".join(parts[3:])
        if sol_str.startswith('"') and sol_str.endswith('"'):
            sol_str = sol_str[1:-1]

        sol = ast.literal_eval(sol_str)
        return algo, dist, sol
    except Exception as e:
        return None


# ================= Worker 封装 =================

def run_sisr(data, vehicle_capcity, file, crt_sisr_log_path, shared_csv, start_time, max_running_time_min, init_route=None):
    sisr_cvrp(
        data, vehicle_capcity,
        inst_name=file,
        inst_log_path=crt_sisr_log_path,
        shared_csv=shared_csv,
        start_time=start_time,
        n_iter=4_00000,  # 4_000
        max_running_time=max_running_time_min / 60,  # hour
        # max_running_time = 1/3600, # hour
        init_T=100.0,
        final_T=1.0,
        n_iter_fleet=None,
        fleet_gap=100,
        obj_n_routes=20,
        init_route=init_route,
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


# ================= 核心管理逻辑 =================

def manage_workers(process_dict, sisr_args, ails_template, filo_template, best_info):
    """
    智能管理进程重启。
    process_dict: {'sisr': proc, 'ails': proc, ...}
    best_info: {'algo': 'source', 'sol': [...], 'dist': 123.4}
    """

    survivor_name = best_info.get('algo')
    best_sol = best_info.get('sol')

    # 1. 终止非幸存者进程
    for name, p in process_dict.items():
        if p and p.is_alive():
            if name == survivor_name:
                continue
            kill_process_tree(p.pid)
            p.join(timeout=1)

    # 2. 垃圾回收 (关键：防止内存泄漏)
    gc.collect()

    # 3. 重启被终止的进程
    # --- SISR ---
    if not process_dict.get('sisr') or not process_dict['sisr'].is_alive():
        # 更新参数（这里需要根据你的实际 sisr 函数签名调整）
        p = multiprocessing.Process(
            target=run_sisr,
            args=(*sisr_args, best_sol),
            name="sisr"
        )
        p.start()
        process_dict['sisr'] = p

    # --- AILS2 (Java) ---
    if not process_dict.get('ails2') or not process_dict['ails2'].is_alive():
        # 传入 JSON 字符串 或者 "None"
        val = best_sol if best_sol else "None"
        cmd = update_cmd_arg(ails_template, "-initSolution", val)
        p = multiprocessing.Process(
            target=run_external_process,
            args=(cmd,),
            name="ails2"
        )
        p.start()
        process_dict['ails2'] = p

    # --- FILO2 (C++) ---
    if not process_dict.get('filo2') or not process_dict['filo2'].is_alive():
        val = best_sol if best_sol else ""
        cmd = update_cmd_arg(filo_template, "--init-solution", val)
        p = multiprocessing.Process(
            target=run_external_process,
            args=(cmd,),
            name="filo2"
        )
        p.start()
        process_dict['filo2'] = p


def update_cmd_arg(base_cmd, flag, value):
    """通用的参数替换函数，替代 index 查找"""
    cmd = base_cmd.copy()
    try:
        idx = cmd.index(flag)
        cmd[idx + 1] = str(value)
    except ValueError:
        pass
    return cmd


# ================= 主程序入口 =================

if __name__ == '__main__':
    # 1. 强制 Spawn
    try:
        multiprocessing.set_start_method('spawn')
    except RuntimeError:
        pass

    # 路径与数据初始化 (简化版)
    instance_name = 'XLTEST-n3101-k685'

    # 使用 pathlib 拼接路径
    instance_path = ROOT_PATH / 'SISR' / 'data' / 'cvrplib_1019' / f'{instance_name}.vrp'

    vrp_data = vrplib.read_instance(str(instance_path))
    vehicle_capacity = vrp_data['capacity']
    data = np.concatenate((vrp_data['node_coord'], vrp_data['demand'][:, None]), axis=1)

    log_path = ROOT_PATH / 'SISR' / 'log_buffer' / instance_name
    log_path.mkdir(parents=True, exist_ok=True)

    # Shared CSV
    shared_csv = log_path / 'shared.csv'
    shared_csv.write_text('', encoding='utf-8')

    # 子目录创建
    sisr_log_path = log_path / 'sisr'
    ails_log_path = log_path / 'ails2'
    filo_log_path = log_path / 'filo2'

    for p in [sisr_log_path, ails_log_path, filo_log_path]:
        p.mkdir(exist_ok=True)

    start_time = time.time()
    # max_running_time_min = inst_size // 25
    max_running_time_min = 3  # TODO: ONLY FOR DEBUG

    # 参数模版 (Template)
    # 将可变参数用占位符或在 build 函数中动态替换
    limit = max_running_time_min * 60
    dMax = 30
    dMin = 15
    gamma = 30
    varphi = 40

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
        "java", "-jar", java_cp,
        "-file", instance_path.as_posix(),
        "-sharedCSV", shared_csv.as_posix(),
        "-logPath", ails_log_path.as_posix(),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None",
        "-limit", str(limit),  # second
        "-stoppingCriterion", "Time",
        "-dMax", str(dMax),
        "-dMin", str(dMin),
        "-gamma", str(gamma),
        "-varphi", str(varphi),
        "-startTime", str(start_time),
    ]

    filo_exe_name = "filo2.exe" if os.name == "nt" else "filo2"
    filo_exe = FILO2_PATH / filo_exe_name

    filo_cmd = [
        str(filo_exe),
        instance_path.as_posix(),
        "--init-solution", "",  # 占位
        "--shared-csv", shared_csv.as_posix(),
        "--start-time", str(start_time),
        "--inst-log-path", filo_log_path.as_posix(),
        "--max-running-seconds", str(max_running_time_min * 60)
    ]

    sisr_args = [
        data,
        vehicle_capacity,
        instance_name,
        str(sisr_log_path),
        str(shared_csv),
        start_time,
        max_running_time_min,
    ]

    # 进程字典
    process_dict = {'sisr': None, 'ails2': None, 'filo2': None}

    # 初始启动
    manage_workers(process_dict, sisr_args, ails_cmd, filo_cmd, {})

    # 【优化2】文件监听循环
    # 使用 open 打开文件，不要在循环里反复 open
    try:
        with open(shared_csv, 'r', encoding='utf-8') as f:
            # 移动到文件末尾
            f.seek(0, 2)

            while True:
                if time.time() - start_time > max_running_time_min * 60:
                    break

                line = f.readline()
                if line:
                    result = parse_solution_line(line)
                    if result:
                        algo, dist, sol = result
                        print(algo, dist)
                        best_info = {'algo': algo, 'dist': dist, 'sol': sol}
                        manage_workers(process_dict, sisr_args, ails_cmd, filo_cmd, best_info)
                else:
                    time.sleep(0.1)

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