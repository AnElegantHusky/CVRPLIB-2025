import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import re


# =============================================================================
# 1. 核心数据读取函数 (Data Loader)
# =============================================================================

def load_results_dataframe(instance_names, algorithm_names, base_dir='.', time_limit=None):
    """
    读取所有实例和算法的结果，返回一个 DataFrame。

    逻辑优先级:
    1. 如果 time_limit is None: 直接读取 .sol 文件。
    2. 如果 time_limit is not None:
       - 尝试读取 .csv 文件。
       - 如果 .csv 非空: 找出 time <= time_limit 的最后一条记录的 fitness。
       - 如果 .csv 为空或不存在: 回退读取 .sol 文件。

    返回:
    pd.DataFrame:
        - Index: Instance Name
        - Columns: Algorithm Names
        - Values: Best Fitness (float) or NaN
    """
    print(f"--- 开始加载数据 (Time Limit: {time_limit if time_limit else 'None'}) ---")

    data_dict = {method: [] for method in algorithm_names}
    indices = []

    for instance in instance_names:
        indices.append(instance)

        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            fitness_val = None

            # --- 路径检查 ---
            if not os.path.isdir(method_dir):
                data_dict[method].append(np.nan)
                continue

            csv_processed = False

            # --- 逻辑分支 A: 尝试读取 CSV (仅当 time_limit 设置时) ---
            if time_limit is not None:
                csv_file_path = None
                # 查找 CSV
                for file in os.listdir(method_dir):
                    if file.endswith('.csv') and instance in file:
                        csv_file_path = os.path.join(method_dir, file)
                        break

                if csv_file_path:
                    try:
                        # 读取 CSV
                        df_temp = pd.read_csv(
                            csv_file_path,
                            sep='[;,]',
                            header=None,
                            names=['time', 'fitness'],
                            engine='python',
                            on_bad_lines='skip'
                        )

                        if not df_temp.empty:
                            # 类型转换与清洗
                            df_temp['time'] = pd.to_numeric(df_temp['time'], errors='coerce')
                            df_temp['fitness'] = pd.to_numeric(df_temp['fitness'], errors='coerce')
                            df_temp.dropna(inplace=True)
                            df_temp.sort_values(by='time', inplace=True)

                            # 筛选时间限制内的数据
                            valid_rows = df_temp[df_temp['time'] <= time_limit]

                            if not valid_rows.empty:
                                fitness_val = valid_rows.iloc[-1]['fitness']
                                csv_processed = True
                            else:
                                # CSV 非空但没有在时间限制内的数据
                                # 这种情况通常意味着在限制时间内未找到可行解
                                csv_processed = True
                                fitness_val = np.nan

                    except Exception as e:
                        print(f"警告: 解析 CSV {csv_file_path} 失败: {e}")

            # --- 逻辑分支 B: 读取 .sol (Fallback) ---
            # 触发条件: time_limit 为 None, 或 CSV 读取并未成功产出结果(且未标记为已处理)
            if fitness_val is None and not csv_processed:
                sol_file_path = None
                for file in os.listdir(method_dir):
                    if file.endswith('.sol') and instance in file:
                        sol_file_path = os.path.join(method_dir, file)
                        break

                if sol_file_path:
                    try:
                        with open(sol_file_path, 'r', encoding='utf-8') as f:
                            # 倒序查找 Cost
                            for line in reversed(f.readlines()):
                                if line.strip().startswith("Cost"):
                                    parts = line.strip().split()
                                    if len(parts) >= 2:
                                        fitness_val = float(parts[1])
                                        break
                    except Exception:
                        pass

            # 将结果存入列表 (如果是 None 转为 NaN)
            data_dict[method].append(fitness_val if fitness_val is not None else np.nan)

    # 构建 DataFrame
    df = pd.DataFrame(data_dict, index=indices)
    print("--- 数据加载完成 ---")
    return df


# =============================================================================
# 2. 绘图与统计函数 (基于 DataFrame)
# =============================================================================

def plot_gap_scatter(df, output_dir='.', show_plot=False, point_size=60, point_alpha=0.7, star_method=None):
    """
    基于结果 DataFrame 绘制 Gap 散点图。
    X轴: 客户数量 (从 index 提取)
    Y轴: Gap %
    """
    print("--- 开始绘制 Gap 散点图 ---")

    # 1. 计算 Gap
    # 计算每行(每个实例)的最小值作为基准
    best_known = df.min(axis=1)

    # 初始化绘图数据列表
    plot_data = []

    for instance in df.index:
        # 尝试提取客户数量 (-n100-)
        match = re.search(r'-n(\d+)-', instance)
        if not match:
            continue
        customer_num = int(match.group(1))

        base_val = best_known[instance]

        if pd.isna(base_val) or base_val == 0:
            continue

        for method in df.columns:
            val = df.loc[instance, method]
            if pd.isna(val):
                continue

            gap = ((val - base_val) / base_val) * 100
            plot_data.append({
                'customer_num': customer_num,
                'method': method,
                'gap': gap
            })

    if not plot_data:
        print("没有有效数据用于绘图。")
        return

    plot_df = pd.DataFrame(plot_data)

    # 2. 绘图
    plt.figure(figsize=(12, 7))

    algorithm_names = df.columns
    for method in algorithm_names:
        method_data = plot_df[plot_df['method'] == method]
        if method_data.empty:
            continue

        marker = 's' if star_method and method == star_method else 'o'

        plt.scatter(
            method_data['customer_num'],
            method_data['gap'],
            label=method,
            s=point_size,
            alpha=point_alpha,
            edgecolors='w',
            linewidths=0.8,
            marker=marker
        )

    plt.xlabel('Number of Customers')
    plt.ylabel('Gap (%)')
    plt.title('Algorithm Gap Analysis')
    plt.legend(title='Method')
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.ylim(bottom=-0.5)  # 稍微留一点底边

    # os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir)
    plt.savefig(output_path, dpi=300)
    print(f"图像已保存至: {output_path}")

    if show_plot:
        plt.show()


def get_fitness_table(df, output_csv=None):
    """
    保存或展示 Fitness 表格 (DataFrame 本身)。
    """
    print("\n--- Fitness 表格预览 ---")
    print(df.head())

    if output_csv:
        os.makedirs(os.path.dirname(output_csv) if os.path.dirname(output_csv) else '.', exist_ok=True)
        df.to_csv(output_csv)
        print(f"表格已保存至: {output_csv}")

    return df


def get_rank_statistics(df, output_csv=None):
    """
    统计排名信息 (Strict Rank 1, Tied Rank 1, Rank 2...)。
    """
    print("\n--- 开始计算排名统计 ---")

    # 1. 计算每个实例的排名 (method='dense': 并列第1均为1，下一个是2)
    # rank 默认对行进行操作吗？axis=1 表示对每行(不同列)进行排名
    ranks_df = df.rank(axis=1, method='dense', ascending=True)

    # 2. 准备统计容器
    # 我们需要区分 Strict Rank 1 (独享) 和 Tied Rank 1 (并列)
    rank_labels = []

    for instance in df.index:
        # 获取该行的排名
        row_ranks = ranks_df.loc[instance]

        # 统计该行有多少个 1.0 (第1名)
        # 注意: 可能会有 NaN，需要忽略
        rank1_count = (row_ranks == 1.0).sum()

        for method in df.columns:
            r = row_ranks[method]
            if pd.isna(r):
                continue

            label = ""
            if r == 1.0:
                label = "Strict Rank 1" if rank1_count == 1 else "Tied Rank 1"
            else:
                label = f"Rank {int(r)}"

            rank_labels.append({
                'Method': method,
                'Rank_Label': label
            })

    if not rank_labels:
        print("无有效数据进行排名。")
        return pd.DataFrame()

    # 3. 生成交叉表
    rank_data = pd.DataFrame(rank_labels)
    rank_table = pd.crosstab(rank_data['Method'], rank_data['Rank_Label'])

    # 4. 列排序 (Strict -> Tied -> Rank 2 -> Rank 3...)
    cols = rank_table.columns.tolist()
    special = ['Strict Rank 1', 'Tied Rank 1']
    others = [c for c in cols if c not in special]
    # 按 Rank 后面的数字排序
    others.sort(key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999)

    final_cols = [c for c in special if c in cols] + others
    rank_table = rank_table[final_cols]

    print(rank_table)

    if output_csv:
        rank_table.to_csv(output_csv)
        print(f"排名统计已保存至: {output_csv}")

    return rank_table


def get_average_gap_statistics(df, output_csv=None, baseline=None):
    """
    计算平均 Gap。
    baseline:
      - None: 默认取每行的最小值作为基准。
      - str: 指定某个算法名称作为基准列。
      - dict: {instance_name: value} 外部基准。
    """
    print(f"\n--- 开始计算平均 Gap (Baseline: {baseline if baseline else 'Best Found'}) ---")

    # 1. 确定基准值列 Series
    if baseline is None:
        base_series = df.min(axis=1)
    elif isinstance(baseline, str):
        if baseline in df.columns:
            base_series = df[baseline]
        else:
            print(f"错误: 基准算法 {baseline} 不在 DataFrame 中。")
            return pd.DataFrame()
    elif isinstance(baseline, dict):
        base_series = pd.Series(baseline)
    else:
        print("不支持的 baseline 类型。")
        return pd.DataFrame()

    # 2. 计算 Gap DataFrame
    # 公式: (Value - Base) / Base * 100
    # 使用 subtract 和 divide 方法以支持自动对齐索引
    gap_df = df.subtract(base_series, axis=0).divide(base_series, axis=0) * 100

    # 3. 计算平均值 (忽略 NaN)
    avg_gaps = gap_df.mean(axis=0).reset_index()
    avg_gaps.columns = ['Method', 'Average Gap (%)']

    # 排序
    avg_gaps.sort_values(by='Average Gap (%)', inplace=True)

    print(avg_gaps)

    if output_csv:
        avg_gaps.to_csv(output_csv, index=False)
        print(f"平均 Gap 已保存至: {output_csv}")

    return avg_gaps