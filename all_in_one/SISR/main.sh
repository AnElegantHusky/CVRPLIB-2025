#!/bin/bash

# 1. 解压文件 (保持不变)
unzip -o instances.zip -d ./data/instances

# 2. 运行 Python 脚本
# $1 代表第一个参数 (start_idx)
# $2 代表第二个参数 (end_idx)
python3 main_bash_generator.py "$1" "$2"

# 3. 执行生成的脚本 (保持不变)
bash run_all.sh