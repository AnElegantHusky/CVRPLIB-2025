import os
import shutil
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor


def safe_copy_atomic(src_file: Path, dest_folder: Path, new_name: str):
    """
    并发安全的复制操作：
    1. 复制到 dest_folder/name.tmp
    2. 原子重命名为 dest_folder/name.sol
    """
    final_path = dest_folder / new_name
    temp_path = dest_folder / f"{new_name.rsplit('.', 1)[0]}.tmp"  # 保持文件名部分，后缀改tmp

    try:
        # 1. 复制成 tmp 文件
        shutil.copy2(src_file, temp_path)

        # 2. 原子重命名 (os.replace 在 POSIX 系统是原子的，且支持覆盖)
        # 这保证了其他程序要么看到旧文件，要么看到完整的新文件，不会看到写入一半的文件
        os.replace(temp_path, final_path)
        return True, f"Atomic Copy: {final_path}"
    except Exception as e:
        if temp_path.exists():
            os.remove(temp_path)  # 清理垃圾
        return False, f"Error copying to {final_path}: {e}"


def process_single_file(sol_file: Path, output_dir_test: Path, output_dir_warm: Path):
    """
    处理单个文件的逻辑
    """
    try:
        # 路径结构: .../instance-name/method-name/*.sol
        # sol_file.parent 是 method-name
        # sol_file.parent.parent 是 instance-name
        instance_name = sol_file.parent.parent.name
        target_filename = f"{instance_name}.sol"

        # -------------------------------------------------
        # 任务 A: 输出到 test_sols (直接复制并重命名)
        # -------------------------------------------------
        dest_test = output_dir_test / target_filename
        shutil.copy2(sol_file, dest_test)

        # -------------------------------------------------
        # 任务 B: 输出到 warm_start_outer_sol (并发安全复制)
        # -------------------------------------------------
        success, msg = safe_copy_atomic(sol_file, output_dir_warm, target_filename)

        if success:
            print(f"[OK] Processed: {instance_name}")
        else:
            print(f"[ERR] {msg}")

    except Exception as e:
        print(f"[FAIL] Failed to process {sol_file}: {e}")


def main():
    # 配置参数
    parser = argparse.ArgumentParser(description="Collect and Rename Solidity Files Safely.")
    parser.add_argument("--src", default="./ails2_restart_sols", help="源文件根目录路径")
    parser.add_argument("--test_out", default="./test_sols", help="普通输出目录")
    parser.add_argument("--warm_out", default="./warm_start_outer_sol", help="并发安全输出目录")

    args = parser.parse_args()

    base_path = Path(args.src)
    test_out = Path(args.test_out)
    warm_out = Path(args.warm_out)

    # 1. 创建目标文件夹
    test_out.mkdir(parents=True, exist_ok=True)
    warm_out.mkdir(parents=True, exist_ok=True)

    # 2. 查找所有符合规则的 .sol 文件
    # glob 模式: */*/*.sol 对应 instance/method/file.sol
    sol_files = list(base_path.glob("*/*/*.sol"))

    if not sol_files:
        print(f"在 {base_path} 下未找到符合 'instance/method/*.sol' 结构的文件。")
        return

    print(f"找到 {len(sol_files)} 个文件，开始处理...")

    # 3. 执行复制 (可以使用线程池加速IO操作，也可以直接循环)
    # 这里使用 ThreadPoolExecutor 来模拟并发环境下的处理能力
    with ThreadPoolExecutor(max_workers=8) as executor:
        for sol in sol_files:
            executor.submit(process_single_file, sol, test_out, warm_out)

    print("所有任务完成。")


if __name__ == "__main__":
    main()