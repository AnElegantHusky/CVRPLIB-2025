import os
import subprocess
import sys
import vrplib
import numpy as np
import time
import pandas as pd
import ast
from sisr2 import sisr_cvrp
import multiprocessing
import traceback
import io

SISR_PATH = os.path.abspath(os.path.dirname(__file__))
ROOT_PATH = os.path.dirname(SISR_PATH)

# python
def run_python_script(script_path, args=None, input_text=None):
    # Use the same Python interpreter that runs this script.
    cmd = [sys.executable, script_path] + (args or [])
    r = subprocess.run(cmd, input=input_text, capture_output=True, text=True)
    print(r.stdout, end='')
    if r.stderr:
        print(r.stderr, file=sys.stderr, end='')
    return r.returncode

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
        verbose_step=100,
        time_window=False,
        soft_time_window=False
    )

# java
# PROJECT_ROOT = 'E:/onedrive/cityU/CVRPLIB/AILS-II/'
# JAVA_CLASSPATH = 'E:/onedrive/cityU/CVRPLIB/AILS-II/target/classes;C:/Users/10525/.m2/repository/org/apache/commons/commons-csv/1.10.0/commons-csv-1.10.0.jar;C:/Users/10525/.m2/repository/org/junit/jupiter/junit-jupiter-api/5.14.0/junit-jupiter-api-5.14.0.jar;C:/Users/10525/.m2/repository/org/opentest4j/opentest4j/1.3.0/opentest4j-1.3.0.jar;C:/Users/10525/.m2/repository/org/junit/platform/junit-platform-commons/1.14.0/junit-platform-commons-1.14.0.jar;C:/Users/10525/.m2/repository/org/apiguardian/apiguardian-api/1.1.2/apiguardian-api-1.1.2.jar;C:/Users/10525/.m2/repository/commons-io/commons-io/2.15.1/commons-io-2.15.1.jar'
# JAVA_ENCODING = '-Dfile.encoding=UTF-8'

# javac -cp "libs/*" -d target/classes src/Auxiliary/*.java src/Data/*.java src/DiversityControl/*.java src/Evaluators/*.java src/Improvement/*.java src/Perturbation/*.java src/SearchMethod/*.java src/Solution/*.java

JAVA_CLASSPATH = f'{ROOT_PATH}/AILS2/target/classes;{ROOT_PATH}/AILS2/libs/commons-csv-1.10.0.jar;{ROOT_PATH}/AILS2/libs/junit-jupiter-api-5.10.2.jar;{ROOT_PATH}/AILS2/libs/junit-jupiter-api-5.14.0.jar;{ROOT_PATH}/AILS2/libs/commons-io-2.15.1.jar'
if os.name == "nt":  # Windows
    pass
else:  # Linux/macOS
    JAVA_CLASSPATH = JAVA_CLASSPATH.replace(';', ':')

def run_java_with_specific_jdk(java_path, args):

    command = [
        'java',
        # JAVA_ENCODING,
        "-classpath", JAVA_CLASSPATH,
        java_path,
    ]
    command.extend(args)

    process = subprocess.Popen(
        command,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        # text=True,
        # encoding='utf-8',
        # cwd=PROJECT_ROOT,
    )

    stdout_bytes, stderr_bytes = process.communicate()

    if stdout_bytes:
        print("Java 输出:", smart_decode(stdout_bytes))
    if stderr_bytes:
        print("Java 报错:", smart_decode(stderr_bytes))


def smart_decode(byte_data):
    if not byte_data:
        return ""

    try:
        return byte_data.decode('utf-8')
    except UnicodeDecodeError:
        try:
            system_encoding = locale.getpreferredencoding()
            return byte_data.decode(system_encoding)
        except:
            return byte_data.decode('utf-8', errors='replace')

# cpp
def run_cpp_program(cpp_path, args):
    if os.name == "nt":  # Windows
        cpp_exe = "{}/filo2.exe".format(cpp_path)
    else:  # Linux/macOS
        cpp_exe = "{}/filo2".format(cpp_path)

    cmd = [cpp_exe] + [str(arg) for arg in args]

    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout_bytes, stderr_bytes = process.communicate()

    if stdout_bytes:
        print("CPP 输出:", smart_decode(stdout_bytes))
    if stderr_bytes:
        print("CPP 报错:", smart_decode(stderr_bytes))


# monitor
def monitor_csv(filename, return_dict):
    if not os.path.exists(filename):
        with open(filename, 'w') as f: pass

    with open(filename, 'r', encoding='utf-8') as f:
        f.seek(0, 2)  # TODO: jump to last
        while True:
            line = f.readline()
            if line:
                print(line)
                df = pd.read_csv(shared_csv)
                last_row = df.iloc[-1]
                pre_best_distance = last_row.iloc[2]
                pre_best_solution = ast.literal_eval(last_row.iloc[3])
                return_dict['best_distance'] = pre_best_distance
                return_dict['best_solution'] = pre_best_solution
            else:
                time.sleep(0.1)


def restart_workers(process_list, sisr_arg, ails_args, filo_args, return_dict, keep_process=None):
    survivor_process = None

    for p in process_list:
        if not p:
            continue
        if keep_process and p.name == keep_process:
            survivor_process = p
            continue

        if p.is_alive():
            p.terminate()
            p.join()

    new_process_list = []

    # --- SISR ---
    if survivor_process and survivor_process.name == "sisr":
        new_process_list.append(survivor_process)
    else:
        p_sisr = multiprocessing.Process(
            target=run_sisr,
            args=(*sisr_arg, return_dict['best_solution']),  # 注意这里可能需要解包
            name="sisr"
        )
        new_process_list.append(p_sisr)

    # --- AILS2 ---
    if survivor_process and survivor_process.name == "ails2":
        new_process_list.append(survivor_process)
    else:
        p_ails = multiprocessing.Process(
            target=run_java_with_specific_jdk,
            args=(AILS2_PATH, ails_args,),
            name="ails2"
        )
        new_process_list.append(p_ails)

    # --- FILO2 ---
    if survivor_process and survivor_process.name == "filo2":
        new_process_list.append(survivor_process)
    else:
        p_filo = multiprocessing.Process(
            target=run_cpp_program,
            args=(FILO2_PATH, filo_args,),
            name="filo2"
        )
        new_process_list.append(p_filo)

    # 3. 启动新进程
    for p in new_process_list:
        if p.pid is None:
            p.start()

    return new_process_list


if __name__ == '__main__':

    # AILS_PATH = 'C:/Users/shunyuyao8/OneDrive/cityU/CVRPLIB/AILS-II/src/SearchMethod/AILSII.java'
    # AILS2_PATH = 'E:/onedrive/cityU/CVRPLIB/AILS-II/src/SearchMethod/AILSII.java'
    # FILO2_PATH = 'E:/onedrive/cityU/CVRPLIB/FILO2/filo2-main/cmake-build-debug/'

    AILS2_PATH = f'SearchMethod/AILSII'
    FILO2_PATH = f'{ROOT_PATH}/FILO2/build/'

    # instance_path = 'E:/onedrive/cityU/CVRPLIB/Baseline/SISRs/SISR-for-VRP-main/data/cvrplib_1019/XLTEST-n3101-k685.vrp'
    # log_path = 'E:/onedrive/cityU/CVRPLIB/Baseline/SISRs/SISR-for-VRP-main/log_buffer/XLTEST-n3101-k685'

    instance_path = f'{ROOT_PATH}/SISR/data/cvrplib_1019/XLTEST-n3101-k685.vrp'
    log_path = f'{ROOT_PATH}/SISR/log_buffer/XLTEST-n3101-k685'
    if not os.path.exists(log_path):
        os.makedirs(log_path)

    # shared info and csv
    instance_name = instance_path.split('/')[-1]
    vrp_data = vrplib.read_instance(instance_path)
    vehicle_capacity = vrp_data['capacity']
    data = np.concatenate((vrp_data['node_coord'], vrp_data['demand'][:, None]), axis=1)
    inst_size = data.shape[0]
    # max_running_time_min = inst_size // 25
    max_running_time_min = 1  # TODO: ONLY FOR DEBUG

    shared_csv = os.path.join(log_path, 'shared.csv').replace("\\", "/")
    open(shared_csv, 'w').close()

    manager = multiprocessing.Manager()
    return_dict = manager.dict()
    return_dict['best_distance'] = None
    return_dict['best_solution'] = None

    start_time = time.time()

    # SISRs log
    crt_sisr_log_path = os.path.join(log_path, 'sisr').replace("\\", "/")
    if not os.path.exists(crt_sisr_log_path):
        os.makedirs(crt_sisr_log_path)

    # AILS log
    crt_ails_log_path = os.path.join(log_path, 'ails2').replace("\\", "/")
    if not os.path.exists(crt_ails_log_path):
        os.makedirs(crt_ails_log_path)

    # FILO log
    crt_filo_log_path = os.path.join(log_path, 'filo2').replace("\\", "/")
    if not os.path.exists(crt_filo_log_path):
        os.makedirs(crt_filo_log_path)

    ## init parameter
    limit = max_running_time_min * 60
    dMax = 30
    dMin = 15
    gamma = 30
    varphi = 40

    ails_args = [
        "-file", instance_path.replace("\\", "/"),
        "-sharedCSV", shared_csv.replace("\\", "/"),
        "-logPath", crt_ails_log_path.replace("\\", "/"),
        "-rounded", "true",
        "-best", "0",
        "-initSolution", "None" if return_dict['best_solution'] is None else return_dict['best_solution'],
        "-limit", str(limit),  # second
        "-stoppingCriterion", "Time",
        "-dMax", str(dMax),
        "-dMin", str(dMin),
        "-gamma", str(gamma),
        "-varphi", str(varphi),
        "-startTime", str(start_time),
    ]

    sisr_args = [
        data,
        vehicle_capacity,
        instance_name,
        crt_sisr_log_path,
        shared_csv,
        start_time,
        max_running_time_min,
    ]

    filo_args = [
        instance_path.replace("\\", "/"),
        "--init-solution", "" if return_dict['best_solution'] is None else return_dict['best_solution'],
        "--shared-csv", shared_csv.replace("\\", "/"),
        "--start-time", str(start_time),
        "--inst-log-path", crt_filo_log_path.replace("\\", "/"),
        "--max-running-seconds", str(max_running_time_min * 60)
    ]

    process_list = []
    process_list = restart_workers(process_list, sisr_args, ails_args, filo_args, return_dict)

    with open(shared_csv, 'r', encoding='utf-8') as f:
        f.seek(0, 2)

        while True:
            if time.time() - start_time > max_running_time_min * 60:
                break

            line = f.readline()
            if line:
                raw_data = line.strip()
                if not raw_data: continue

                try:
                    line_df = pd.read_csv(io.StringIO(line), header=None)
                    pre_best_algorithm = line_df.iloc[0, 0]
                    pre_best_distance = line_df.iloc[0, 2]
                    pre_best_solution = ast.literal_eval(line_df.iloc[0, 3])

                    return_dict['best_distance'] = pre_best_distance
                    return_dict['best_solution'] = pre_best_solution

                    # args update
                    # sisr_args doesn't need
                    # ails_args
                    ails_args[11] = str(pre_best_solution)

                    # filo_args
                    filo_args[2] = str(pre_best_solution)

                    process_list = restart_workers(process_list, sisr_args, ails_args, filo_args, return_dict, pre_best_algorithm)

                except Exception as e:
                    print(f"main error: ")
                    traceback.print_exc()

            time.sleep(0.1)

    for p in process_list:
        if p.is_alive():
            p.terminate()

