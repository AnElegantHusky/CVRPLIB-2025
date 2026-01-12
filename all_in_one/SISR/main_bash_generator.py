# from pathlib import Path
#
#
# SISR_PATH = Path(__file__).resolve().parent
# ROOT_PATH = SISR_PATH.parent
#
# instance_folder = 'cvrplib_1019' # TODO: check path
# instance_root_path = SISR_PATH / 'data' / instance_folder
#
# sh_name = 'run_all.sh'
#
# lines = [
#     "#!/bin/bash",
#     "",
# ]
# for instance_path in instance_root_path.rglob('*.vrp'):
#     instance_name = instance_path.name
#     cmd = f"nohup python main_for_all_final.py {instance_folder} {instance_name} > {instance_name}.log 2>&1 &"
#     lines.append(cmd)
#
# with open(sh_name, 'w', encoding='utf-8') as f:
#     f.write("\n".join(lines))
#     f.write("\n")  # 文件末尾加个换行是个好习惯
#

import sys
from pathlib import Path

# 1. 定义路径
SISR_PATH = Path(__file__).resolve().parent
ROOT_PATH = SISR_PATH.parent

instance_folder = 'instances' # TODO: check path
instance_root_path = SISR_PATH / 'data' / instance_folder

# 2. 获取所有文件并【排序】
# 必须先获取列表才能知道总长度，用于默认情况
all_files = sorted(list(instance_root_path.rglob('*.vrp')))
total_count = len(all_files)

# 3. 处理参数逻辑
if len(sys.argv) >= 3:
    # 指定了区间
    try:
        start_idx = int(sys.argv[1])
        end_idx = int(sys.argv[2])
    except ValueError:
        # 如果参数格式错误，直接退出，不打印信息
        sys.exit(1)
else:
    # 未指定区间，默认跑全部
    start_idx = 0
    end_idx = total_count
    # 默认文件名

sh_name = 'run_all.sh'

# 4. 根据索引切片 (左闭右开)
# Python切片特性：如果 end_idx 超过列表长度，不会报错，而是取到末尾
target_files = all_files[start_idx:end_idx]

lines = [
    "#!/bin/bash",
    "",
]

for instance_path in target_files:
    instance_name = instance_path.stem
    cmd = f"nohup python main_for_all_final.py {instance_folder} {instance_name} > {instance_name}.log 2>&1 &"
    lines.append(cmd)

with open(sh_name, 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))
    f.write("\n")
