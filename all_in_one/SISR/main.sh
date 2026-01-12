#!/bin/bash

# 1. 前置准备工作 (保持不变)
# -------------------------------------------------
# 确保脚本在正确的目录下运行（可选，但推荐加上，防止路径错乱）
# cd "$(dirname "$0")" || exit 1

rm -rf ./data/instances
unzip -o instances.zip -d ./data/instances
# -------------------------------------------------


# 2. 定义要执行的命令 (把参数 $1 $2 传进去)
# -------------------------------------------------
# 这样写可以避免下面代码重复，且方便修改
# 注意：这里我们只定义后续要跑的命令字符串
CMD="python3 main_bash_generator.py $1 $2 && bash run_all.sh"


# 3. 智能路径检测与执行
# -------------------------------------------------
echo "正在检测容器内的目录结构..."

# 【尝试路径 A】: /app/all_in_one/SISR
# docker exec ... test -d 判断目录是否存在。如果不报错(返回0)，说明目录存在。
if docker exec cvrplib test -d /app/all_in_one/SISR; then
    echo "✅ 检测到路径 A: /app/all_in_one/SISR"
    echo "🚀 开始执行任务..."

    # 执行命令并直接退出脚本
    # 注意：cd 必须写在 bash -c 里面
    docker exec -w /app cvrplib bash -c "cd all_in_one/SISR && $CMD"
    exit $?

# 【尝试路径 B】: /app/SISR
elif docker exec cvrplib test -d /app/SISR; then
    echo "✅ 检测到路径 B: /app/SISR"
    echo "🚀 开始执行任务..."

    docker exec -w /app cvrplib bash -c "cd SISR && $CMD"
    exit $?

# 【所有路径都失败】
else
    echo "❌ 错误: 在容器 cvrplib 中未找到 /app/all_in_one/SISR 或 /app/SISR 路径。"
    exit 1
fi