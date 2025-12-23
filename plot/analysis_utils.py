import os
import pandas as pd
import numpy as np


def load_results_as_dataframe(instance_names, algorithm_names, base_dir='.', baseline=None):
    """
    读取算法结果并返回两个 DataFrame:
    1. fitness_df: 目标函数值 (Cost)
    2. gap_df: 相对 Gap (%)

    参数:
    instance_names (list): 实例名称列表 (不带 .vrp/.sol 后缀)
    algorithm_names (list): 算法名称列表 (对应文件夹名)
    base_dir (str): 数据根目录
    baseline (str/dict/None):
        - None: 以当前所有算法中的最小值 (Best Found) 为基准。
        - str: 指定某个算法名作为基准 (如 'Gurobi')。
        - dict: {instance_name: optimal_value} 外部字典。

    返回:
    fitness_df (pd.DataFrame), gap_df (pd.DataFrame)
    """

    # 初始化数据字典: data[instance_name][algo_name] = fitness
    data = {}

    print(f"--- 正在加载 {len(instance_names)} 个实例和 {len(algorithm_names)} 个算法的数据 ---")

    for instance in instance_names:
        data[instance] = {}

        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            fitness_val = np.nan  # 默认为 NaN

            # 1. 优先查找 .sol 文件 (通常包含最终 Cost)
            file_path = None
            if os.path.isdir(method_dir):
                for file in os.listdir(method_dir):
                    # 匹配文件名包含实例名且以 .sol 结尾
                    if file.endswith('.sol') and instance in file:
                        file_path = os.path.join(method_dir, file)
                        break

            # 2. 读取 Fitness
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 倒序查找 Cost 行
                        for line in reversed(lines):
                            if line.strip().startswith("Cost"):
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    fitness_val = float(parts[1])
                                    break
                except Exception as e:
                    print(f"读取错误 {file_path}: {e}")

            # 存入字典
            data[instance][method] = fitness_val

    # --- 构建 Fitness DataFrame ---
    fitness_df = pd.DataFrame.from_dict(data, orient='index')
    # 确保列顺序与 algorithm_names 一致
    fitness_df = fitness_df.reindex(columns=algorithm_names)

    print("Fitness 数据加载完成。")

    # --- 构建 Gap DataFrame ---
    gap_df = pd.DataFrame(index=fitness_df.index, columns=fitness_df.columns)

    # 确定基准值 (Base Values)
    base_values = pd.Series(index=fitness_df.index, dtype=float)

    if baseline is None:
        # 默认模式: 行最小值 (Best Found among algos)
        base_values = fitness_df.min(axis=1)
        print("基准: 当前对比算法中的最小值 (Best Found)")
    elif isinstance(baseline, str):
        # 算法模式: 指定某一列作为基准
        if baseline in fitness_df.columns:
            base_values = fitness_df[baseline]
            print(f"基准: 算法 '{baseline}'")
        else:
            print(f"错误: 基准算法 '{baseline}' 不在数据中，无法计算 Gap。")
            return fitness_df, pd.DataFrame()
    elif isinstance(baseline, dict):
        # 字典模式: 外部 BKS
        # map会自动匹配 index (instance name)
        base_values = fitness_df.index.map(baseline)
        print("基准: 外部提供的 BKS 字典")

    # 计算 Gap (%)
    # 公式: (Val - Base) / Base * 100
    # 注意处理 Base 为 0 或 NaN 的情况
    for col in fitness_df.columns:
        # 向量化计算
        gap_df[col] = ((fitness_df[col] - base_values) / base_values) * 100

    # 清理: 如果 Base 是 NaN，Gap 也是 NaN；如果 Base 是 0 且 Cost > 0，Gap 为 inf

    return fitness_df, gap_df


def analyze_difficulty(gap_df, top_k=5, output_csv=None, methods_to_show=None):
    """
    分析 Gap 矩阵。

    参数:
    gap_df (pd.DataFrame): Gap 数据表
    top_k (int): 显示前K个
    output_csv (str): 导出CSV路径
    methods_to_show (str | list | None):
        - None: 默认，打印所有算法。
        - str: 只打印指定的一个算法，例如 'AILS-II'。
        - list: 打印指定的列表，例如 ['AILS-II', 'GA']。
    """
    print("\n" + "=" * 60)
    print(f"   深度难度分析 (Based on Gap %)")
    print("=" * 60)

    # --- 1. 处理 methods_to_show 参数 ---
    target_methods = []

    if methods_to_show is None:
        target_methods = gap_df.columns.tolist()
    elif isinstance(methods_to_show, str):
        target_methods = [methods_to_show]
    elif isinstance(methods_to_show, list):
        target_methods = methods_to_show
    else:
        print(f"参数错误: methods_to_show 类型不支持 ({type(methods_to_show)})，将显示所有方法。")
        target_methods = gap_df.columns.tolist()

    # 检查请求的方法是否在 DataFrame 中
    valid_methods = []
    for m in target_methods:
        if m in gap_df.columns:
            valid_methods.append(m)
        else:
            print(f"警告: 算法 '{m}' 不在数据中，已跳过。")

    if not valid_methods:
        print("没有有效的算法可供分析。")
        return

    summary_list = []
    EPSILON = 1e-4

    # --- 2. 遍历筛选后的方法 ---
    for method in valid_methods:
        series = gap_df[method].dropna()

        if series.empty:
            print(f"\n算法: [{method}] - 无有效数据")
            continue

        min_gap = series.min()
        max_gap = series.max()
        avg_gap = series.mean()

        bks_count = (series < -EPSILON).sum()
        new_best_count = (series < -EPSILON).sum()

        print(f"\n🔹 算法: [{method}]")
        print(f"  - 最小 Gap: {min_gap:+.4f}%")
        print(f"  - 平均 Gap: {avg_gap:.4f}%")
        print(f"  - 最大 Gap: {max_gap:.4f}%")
        print(f"  - 达到/超越 BKS 数量: {bks_count} (其中严格超越: {new_best_count})")

        # [Tier 1] 达到或超越 BKS
        winners = series[series <= EPSILON].sort_values(ascending=True)
        if not winners.empty:
            print(f"  ✅ [Tier 1] 达到或超越 BKS 的实例 (共 {len(winners)} 个):")
            for inst, gap in winners.items():
                marker = "🌟 NEW BEST!" if gap < -EPSILON else "   (Matches BKS)"
                print(f"     {inst:<20} : {gap:+.4f}% {marker}")
        else:
            print(f"  ⚠️ [Tier 1] 没有达到 BKS 的实例。")

        # [Tier 2] 接近 BKS 的 Top K
        others = series[series > EPSILON].sort_values(ascending=True).head(top_k)
        if not others.empty:
            print(f"  🥈 [Tier 2] 接近 BKS 的前 {top_k} 个实例 (Positive Gaps):")
            for inst, gap in others.items():
                print(f"     {inst:<20} : {gap:+.4f}%")

        # [Bottom] 最差实例
        worst_instances = series.sort_values(ascending=False).head(top_k)
        print(f"  ❌ [Bottom {top_k}] 最困难的实例 (Worst Gaps):")
        for inst, gap in worst_instances.items():
            print(f"     {inst:<20} : {gap:+.4f}%")

        summary_list.append({
            'Method': method,
            'Min Gap': min_gap,
            'Avg Gap': avg_gap,
            'Max Gap': max_gap,
            '# Beat/Match BKS': bks_count,
            '# Strictly Beat BKS': new_best_count,
            'Hardest Instance': worst_instances.index[0] if not worst_instances.empty else None
        })

    if output_csv:
        summary_df = pd.DataFrame(summary_list)
        cols = ['Method', 'Min Gap', 'Avg Gap', 'Max Gap', '# Beat/Match BKS', '# Strictly Beat BKS',
                'Hardest Instance']
        # 确保只包含存在的列（防止某些情况下列名对不上）
        cols = [c for c in cols if c in summary_df.columns]
        summary_df = summary_df[cols]
        summary_df.to_csv(output_csv, index=False)
        print(f"\n摘要统计已保存至: {output_csv}")