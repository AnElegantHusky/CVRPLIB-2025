import logging
import os
from pathlib import Path

from src.kgls import KGLS

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 1. 获取脚本文件所在的目录 (e.g., CVRP-2025/scripts)
script_dir = Path(__file__).resolve().parent

# 2. 获取项目根目录 (e.g., CVRP-2025)
# 脚本位于 'scripts' 目录下，所以父目录就是项目根目录
project_root = script_dir.parent

# 3. 实例文件所在的目录 (e.g., CVRP-2025/XLDemo)
instance_dir = project_root / 'XLDemo'

# 4. 结果文件保存的目录 (e.g., CVRP-2025/results/kgls)
results_dir = project_root / 'results' / 'kgls'

# 确保结果目录存在
results_dir.mkdir(parents=True, exist_ok=True)

# 遍历 XLDemo 目录下的所有 .vrp 文件
# 使用 glob('*.vrp') 来查找匹配模式的文件
for file_path in instance_dir.glob('*.vrp'):
    try:
        # 提取文件名（不包含目录）
        file_name = file_path.name
        # 提取文件名（不包含扩展名）
        base_name = file_path.stem
        # 构建输出文件的路径
        # 结果文件名通常为 实例名.sol 或 实例名_result.txt
        output_file_name = f"{file_name}.sol"  # 假设保存为 .sol 文件
        record_file_name = f"{file_name}.sol.csv"
        output_path = results_dir / output_file_name
        record_path = results_dir / record_file_name

        print('-'*40)
        logger.info(f"Processing instance: {file_name}")

        kgls_runner = KGLS(path_to_instance_file=str(file_path), record_path=record_path, depth_lin_kernighan=2)
        runtime_min = kgls_runner.nodes_number // 25
        runtime_s = runtime_min * 60
        kgls_runner.set_abortion_condition(condition_name="max_runtime", param=runtime_s)

        kgls_runner.run(visualize_progress=False)

        # 保存最佳解到文件
        # 假设 kgls.best_solution_to_file() 是一个在 kgls_runner 实例上的方法
        kgls_runner.best_solution_to_file(str(output_path))

        logger.info(f"Successfully processed {file_name}. Result saved to {output_path}")

    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}", exc_info=True)

logger.info("All instances processed.")