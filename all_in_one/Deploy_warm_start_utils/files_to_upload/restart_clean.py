import os
import shutil
import time
from datetime import datetime
from pathlib import Path

# 确保能引用到同级目录下的模块
from extract_survivor_history import extract_solutions

# === 配置 ===
# 假设脚本位于 SISR 目录下 (容器工作目录)
BASE_DIR = Path(__file__).resolve().parent
LOG_BUFFER_DIR = BASE_DIR / 'log_buffer'
OUTPUT_SOL_DIR = BASE_DIR / 'ails2_restart_sols'

# 定义需要提取的算法配置 (按需修改)
EXTRACT_ALGOS = [
    "ails2_etaMax1.000_stoppingTime1296000.00",  # 15 天
    "ails2_etaMax1.000_stoppingTime1728000.00",  # 20 天
]


def clean_and_prepare():
    print(f"[*] Starting Environment Cleanup & Preparation...")
    print(f"    Base Dir: {BASE_DIR}")

    # 1. 提取历史解 (Extract)
    # 这一步会读取 log_buffer 里的 DB，把解写到 output 文件夹 (默认 extract_survivor_history 逻辑)
    # 我们先定义一个临时输出目录，或者直接提取到目标目录
    print(f"[*] Step 1: Extracting solutions from DB...")

    # 确保输出目录存在且为空 (或清空它)
    if OUTPUT_SOL_DIR.exists():
        print(f"    Cleaning old solution dir: {OUTPUT_SOL_DIR}")
        shutil.rmtree(OUTPUT_SOL_DIR)
    OUTPUT_SOL_DIR.mkdir(parents=True, exist_ok=True)

    try:
        # 调用提取函数
        # 注意：你需要确保 extract_survivor_history.py 的 extract_solutions 函数
        # 接受 output_path 参数，或者它默认输出到 ./output，我们需要移动它
        # 假设 extract_solutions 签名是 (root_path, algos, topk, output_base_path)
        # 如果不是，请根据实际情况调整调用

        # 这里假设 extract_survivor_history 默认生成在 ./output 目录下
        extract_solutions(
            LOG_BUFFER_DIR,
            OUTPUT_SOL_DIR,
            EXTRACT_ALGOS,
            top_k=1
        )

        # 将生成的 output 文件夹移动/重命名为 ails2_restart_sols
        default_output = BASE_DIR / "output"
        if default_output.exists():
            # 将 output 下的内容移动到 OUTPUT_SOL_DIR
            # 或者直接重命名 output -> ails2_restart_sols
            # 这里采用覆盖式移动策略
            for item in default_output.iterdir():
                shutil.move(str(item), str(OUTPUT_SOL_DIR))
            shutil.rmtree(default_output)  # 删掉空的 output
            print(f"    ✅ Solutions moved to {OUTPUT_SOL_DIR}")
        else:
            print(f"    ⚠️ No output generated (DB might be empty).")

    except Exception as e:
        print(f"    ❌ Extraction failed: {e}")
        # 不中断，继续尝试存档 Log

    # 2. 存档旧 Log (Archive)
    print(f"[*] Step 2: Archiving old log_buffer...")
    if LOG_BUFFER_DIR.exists():
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{date_str}_log_buffer"
        archive_path = BASE_DIR / archive_name

        try:
            shutil.move(str(LOG_BUFFER_DIR), str(archive_path))
            print(f"    ✅ Archived log_buffer to: {archive_name}")
        except Exception as e:
            print(f"    ❌ Archive failed: {e}")
    else:
        print(f"    ⚠️ No log_buffer found to archive.")

    # 3. 重建空的 log_buffer (为接下来的运行做准备)
    if not LOG_BUFFER_DIR.exists():
        LOG_BUFFER_DIR.mkdir()
        # 设为 777 权限防止 Docker 权限问题
        try:
            os.chmod(LOG_BUFFER_DIR, 0o777)
        except:
            pass
        print(f"    ✅ Recreated empty log_buffer.")


if __name__ == "__main__":
    clean_and_prepare()