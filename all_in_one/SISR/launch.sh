#!/bin/bash

# 定义 Maven 的 SSL 忽略参数
MAVEN_SSL_OPTS="-Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true"

# 用于记录结果的数组
success_list=()
failure_list=()

echo "开始执行批量构建任务..."
echo "=========================================="

# 遍历当前目录下所有的文件夹
for dir in */; do
    dir=${dir%/} # 去掉末尾斜杠

    # 检查是否为目录（排除脚本自身或文件）
    [ -d "$dir" ] || continue

    cmd=""
    # 根据目录名确定执行指令
    if [[ "$dir" == HGS* ]] || [[ "$dir" == "FILO2" ]]; then
        cmd="bash rebuild_sy.sh"
    elif [[ "$dir" == AILS2* ]]; then
        cmd="mvn clean package $MAVEN_SSL_OPTS"
    else
        continue # 不属于目标目录则跳过
    fi

    echo "[正在构建] 目录: $dir"
    echo "执行命令: $cmd"

    # 在子 Shell 中执行，并获取退出状态码 ($?)
    # 这里的 (cd ... && ...) 保证了路径切换不影响主脚本
    if (cd "$dir" && eval "$cmd"); then
        echo -e "\033[32m[成功] $dir 构建完成\033[0m"
        success_list+=("$dir")
    else
        echo -e "\033[31m[失败] $dir 构建过程中出现错误\033[0m"
        failure_list+=("$dir")
    fi
    echo "------------------------------------------"
done

# --- 最终汇总报告 ---
echo -e "\n=========================================="
echo "                构建总结报告"
echo "=========================================="
echo "总计任务数: $(( ${#success_list[@]} + ${#failure_list[@]} ))"
echo -e "成功数量: \033[32m${#success_list[@]}\033[0m"
echo -e "失败数量: \033[31m${#failure_list[@]}\033[0m"

if [ ${#failure_list[@]} -ne 0 ]; then
    echo -e "\n以下项目构建失败，请检查相关日志："
    for fail in "${failure_list[@]}"; do
        echo -e "  - \033[31m$fail\033[0m"
    done
else
    echo -e "\n\033[32m恭喜！所有项目均构建成功。\033[0m"
fi
echo "=========================================="