#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import logging
import subprocess
import concurrent.futures
from typing import Tuple
import argparse

# ================= 配置区域 =================

# 1. 脚本所在目录
SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))

# 2. AILSII Jar包路径 (假设在 bin 文件夹下)
# JAR_NAME = "AILS-II_parallel_debug.jar"
JAR_NAME = "AILS2_Eta_Cycle.jar"


JAR_PATH = os.path.join(SCRIPT_DIR, "bin", JAR_NAME)

# 3. 实例文件所在文件夹 (根据你的命令行，这里是 XLDemo)
INSTANCES_DIR = os.path.join(SCRIPT_DIR, "XLTEST")

# 4. 结果输出根目录
# etaMax = 0.2
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "remote_results", JAR_NAME).removesuffix('.jar')
RESUME_DIR = os.path.join(SCRIPT_DIR, 'remote_results/test-5days', 'AILSII_origin_5d')

# 5. 硬编码的任务列表 (文件名, 时间限制秒)
# 这些是根据你提供的 hgs 命令行提取的
# TARGET_TASKS = [
#     # ("XLTEST-n1048-k139.vrp", 2460, 246, 0.8, "true"),
#     # ("XLTEST-n2168-k625.vrp", 5160),
#     # ("XLTEST-n3101-k685.vrp", 7440),
#     # ("XLTEST-n4245-k164.vrp", 10140),
#     # ("XLTEST-n5174-k170.vrp", 12360),
#     # ("XLTEST-n5649-k365.vrp", 13500),
#     # ("XLTEST-n6034-k1234.vrp", 14460),
#     ("XLTEST-n8575-k343.vrp", 20580, 2058, etaMax, "true")
# ]

TARGET_INSTANCES = [
    "XLTEST-n1048-k139.vrp",
    "XLTEST-n2168-k625.vrp",
    "XLTEST-n3101-k685.vrp",
    "XLTEST-n4245-k164.vrp",
    "XLTEST-n5174-k170.vrp",
    "XLTEST-n5649-k365.vrp",
    "XLTEST-n6034-k1234.vrp",
    "XLTEST-n8575-k343.vrp",
]

CYCLE = [3600, 1800]

ETA_MAX = [1, 0.75, 0.5, 0.25, 0.1, 0.05]

TASK_LIST = []
for instance in TARGET_INSTANCES:
    for cycle in CYCLE:
        for eta in ETA_MAX:
            time_limit = 24 * 3600  # 1 day
            # time_limit = 1  # 1 day
            TASK_LIST.append((instance, time_limit, cycle, eta, "true"))

# 6. 并行设置
# None = 使用所有CPU核心。如果内存不足，请手动设置为整数，例如 4
MAX_WORKERS = None

# 7. Java 堆内存设置
JAVA_XMS = "6000m"
JAVA_XMX = "6000m"

JAVA_EXE_PATH = "D:\\.jdks\\corretto-24.0.2\\bin\\java.exe"

# ===========================================

# 日志配置
LOG_FILE = os.path.join(SCRIPT_DIR, "log", "ailsii_experiment.log")
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, mode='w'),
        logging.StreamHandler()
    ]
)


def run_single_task(task: Tuple[str, int, int, float, str]):
    """
    运行单个 AILSII 任务
    """
    instance_filename, time_limit, cycle, resetEta, printEta = task
    instance_name = os.path.basename(instance_filename).removesuffix('.vrp')
    instance_path = os.path.join(INSTANCES_DIR, instance_filename)

    # 准备日志前缀
    log_prefix = f"[{instance_filename} | {time_limit}s]"

    # 1. 检查文件是否存在
    if not os.path.exists(instance_path):
        logging.error(f"{log_prefix} 实例文件未找到: {instance_path}")
        return

    # 2. 准备输出文件 (CSV)
    # AILSII 的控制台输出通常包含统计信息，原脚本将其重定向到 csv
    # output_csv_path = os.path.join(OUTPUT_DIR + f'_{cycle}_{resetEta}', f"{instance_filename}.csv")
    output_csv_path = OUTPUT_DIR + f'_continue_{cycle}_{resetEta}'

    try:
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    except OSError as e:
        logging.error(f"{log_prefix} 无法创建输出目录: {e}")
        return

    # 3. 构建命令
    # 对应原命令: java -jar ... bin/AILSII_CPU.jar -file ... -limit ...
    command = [
        "java", "-jar",
        f"-Xms{JAVA_XMS}", f"-Xmx{JAVA_XMX}",
        JAR_PATH,
        "-file", instance_path,
        "-rounded", "true",
        "-stoppingCriterion", "Time",
        "-limit", str(time_limit),
        '-output', output_csv_path,
        '-resume', f'{os.path.join(RESUME_DIR, instance_name)}.sol',
        '-cycle', str(cycle),
        '-resetEta', str(resetEta),
        '-printEta', printEta
    ]
    # command = [
    #     "java", "-jar",
    #     f"-Xms{JAVA_XMS}", f"-Xmx{JAVA_XMX}",
    #     JAR_PATH,
    #     "-file", instance_path,
    #     "-rounded", "true",
    #     "-stoppingCriterion", "Time",
    #     "-limit", str(time_limit)
    # ]

    # logging.info(f"{log_prefix} 开始运行...")
    # logging.info(f"CMD: {' '.join(command)}") # 如果需要调试命令可取消注释

    try:
        # 4. 执行命令并重定向 stdout 到文件
        # with open(output_csv_path, 'w') as output_file:
        subprocess.run(
            command,
            # stdout=output_file,  # 将标准输出写入 .csv 文件
            # stderr=subprocess.PIPE,  # 捕获错误输出以便在日志显示
            text=True,
            check=True
        )

        # logging.info(f"{log_prefix} 完成。日志已保存至 {output_csv_path}")

    except subprocess.CalledProcessError as e:
        logging.error(f"{log_prefix} 运行失败 (Exit Code: {e.returncode})")
        if e.stderr:
            logging.error(f"{log_prefix} STDERR: {e.stderr.strip()}")
    except Exception as e:
        logging.error(f"{log_prefix} 发生未知错误: {e}")


def main():
    parser = argparse.ArgumentParser(description="AILSII 专项测试脚本")
    parser.add_argument('--start_idx', type=int, default=0, help='任务起始索引 (包含)')
    parser.add_argument('--end_idx', type=int, default=None, help='任务结束索引 (不包含，默认为列表末尾)')
    args = parser.parse_args()

    logging.info("--- AILSII 专项测试脚本启动 ---")
    # logging.info(f"目标任务数: {len(TARGET_TASKS)}")

    if not os.path.exists(JAR_PATH):
        logging.critical(f"找不到 Jar 文件: {JAR_PATH}")
        return

    if not os.path.exists(INSTANCES_DIR):
        logging.critical(f"找不到实例文件夹: {INSTANCES_DIR}")
        return

    target_tasks = TASK_LIST[args.start_idx: args.end_idx]
    # 使用进程池并行执行
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # if MAX_WORKERS:
        #     logging.info(f"并行进程数: {MAX_WORKERS}")
        # else:
        #     logging.info("并行进程数: 自动 (所有核心)")

        list(executor.map(run_single_task, target_tasks))

    # logging.info("--- 所有任务已结束 ---")


if __name__ == "__main__":
    main()