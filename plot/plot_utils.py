import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import re

def plot_search_curves(instance_name, algorithm_names, base_dir='.', output_dir='.', show_plot=False):
    """
    绘制指定实例在所有算法下的时间-Fitness搜索曲线。

    参数:
    instance_name (str): 要绘制的实例名称 (例如 'instance_A')。
    algorithm_names (list): 包含所有算法 (method) 名称的列表。
                            这些名称对应于 'base_dir' 下的子目录。
    base_dir (str, optional): 存放所有算法目录的基础路径。默认为当前目录 '.'。
    """

    plt.figure(figsize=(12, 7))

    print(f"--- 开始绘制实例: {instance_name} ---")

    found_data = False  # 标记是否找到了任何数据

    # 1. 遍历所有算法 (method)
    for method in algorithm_names:
        method_dir = os.path.join(base_dir, method)

        # 检查算法目录是否存在
        if not os.path.isdir(method_dir):
            print(f"信息: 目录 {method_dir} 不存在, 跳过。")
            continue

        # 2. 查找文件：
        # 根据您的描述 "method/instance_name.csv"
        # 我们将查找完全匹配的文件名

        file_path = None
        for file in os.listdir(method_dir):
            if file.endswith('.csv') and instance_name in file:
                file_path = os.path.join(method_dir, file)

        # if not os.path.exists(file_path):
        if file_path is None:
            # 如果严格匹配的文件不存在，打印警告并跳过
            # (如果想实现“包含”，需要用 os.listdir 遍历，这里按您给的结构来)
            print(f"信息: 文件 {file_path} 未找到, 跳过。")
            continue

        # 3. 读取CSV文件
        try:
            # 使用 pandas 读取, sep='[;,]' 使用正则表达式匹配逗号或分号
            # header=None 表示文件没有标题行
            # names=['time', 'fitness'] 指定列名
            # engine='python' 是使用正则表达式分隔符所必需的
            data = pd.read_csv(
                file_path,
                sep='[;,]',
                header=None,
                names=['time', 'fitness'],
                engine='python',
                on_bad_lines='skip'  # 跳过格式错误的行
            )

            # 检查是否读到了空文件
            if data.empty:
                print(f"警告: 文件 {file_path} 为空, 跳过。")
                continue

            # 确保数据是数值类型
            data['time'] = pd.to_numeric(data['time'], errors='coerce')
            data['fitness'] = pd.to_numeric(data['fitness'], errors='coerce')

            # 丢弃转换失败的行 (如果存在)
            data.dropna(inplace=True)

            # 确保数据按时间排序
            data = data.sort_values(by='time')

            print(f"{method}: {len(data)} entries | best fitness: {data['fitness'].iloc[-1]}")
            found_data = True

            # 4. 绘制折线图
            # 使用 'label=method' 以便图例显示算法名称
            plt.plot(data['time'], data['fitness'], label=method, marker='o', markersize=2, linestyle='-')

        except pd.errors.EmptyDataError:
            print(f"警告: 文件 {file_path} 为空, 跳过。")
        except Exception as e:
            print(f"错误: 读取或处理 {file_path} 时出错: {e}")

    # 5. 美化和显示图表
    if not found_data:
        print(f"--- 实例 {instance_name} 未找到任何有效数据, 无法绘图。 ---")
        plt.close()  # 关闭空白的图形窗口
        return

    plt.xlabel('Time')
    plt.ylabel('Fitness')
    plt.title(f'"{instance_name}" Time vs. Fitness')
    plt.legend(title='Method')  # 添加图例
    plt.grid(True, linestyle='--', alpha=0.6)  # 添加网格线
    plt.tight_layout()  # 自动调整布局

    # 保存图像或显示图像
    output_filename = f"{output_dir}\plot_{instance_name}.png"
    plt.savefig(output_filename)
    print(f"--- 绘图完成: {instance_name}, 图像已保存至 {output_filename} ---")
    if show_plot:
        plt.show()


def plot_best_fitness(instance_name, algorithm_names, base_dir='.', output_dir='.', show_plot=False):
    """
    绘制指定实例在所有算法下的【最佳】Fitness收敛曲线（单调递减）。

    参数:
    instance_name (str): 要绘制的实例名称 (例如 'instance_A')。
    algorithm_names (list): 包含所有算法 (method) 名称的列表。
    base_dir (str, optional): 存放所有算法目录的基础路径。默认为 '.'。
    output_dir (str, optional): 图像保存目录。默认为 '.'。
    """

    plt.figure(figsize=(12, 7))

    print(f"--- 开始绘制【最佳Fitness】曲线: {instance_name} ---")

    found_data = False  # 标记是否找到了任何数据

    # 1. 遍历所有算法 (method)
    for method in algorithm_names:
        method_dir = os.path.join(base_dir, method)

        if not os.path.isdir(method_dir):
            print(f"信息: 目录 {method_dir} 不存在, 跳过。")
            continue

        # 2. 查找文件
        file_path = None
        for file in os.listdir(method_dir):
            if file.endswith('.csv') and instance_name in file:
                file_path = os.path.join(method_dir, file)

        # if not os.path.exists(file_path):
        if file_path is None:
            print(f"信息: 文件 {file_path} 未找到, 跳过。")
            continue

        # 3. 读取CSV文件
        try:
            data = pd.read_csv(
                file_path,
                sep='[;,]',
                header=None,
                names=['time', 'fitness'],
                engine='python',
                on_bad_lines='skip'
            )

            if data.empty:
                print(f"警告: 文件 {file_path} 为空, 跳过。")
                continue

            data['time'] = pd.to_numeric(data['time'], errors='coerce')
            data['fitness'] = pd.to_numeric(data['fitness'], errors='coerce')
            data.dropna(inplace=True)

            # 确保数据按时间排序
            data = data.sort_values(by='time').reset_index(drop=True)

            if data.empty:
                print(f"警告: {file_path} 在清理后为空, 跳过。")
                continue

            # ****************************************************
            # ** 核心改动：计算单调递减的 "Best Fitness" **
            #
            # .cummin() 会计算到当前行为止的累积最小值。
            # 这确保了曲线只会下降或保持水平，绝不会上升。
            data['best_fitness'] = data['fitness'].cummin()
            # ****************************************************

            print(f"{method}: {len(data)} entries | best fitness: {data['fitness'].iloc[-1]}")
            found_data = True

            # 4. 绘制折线图 (使用 'best_fitness' 列)
            plt.plot(data['time'], data['best_fitness'], label=method, marker='o', markersize=2, linestyle='-')

        except pd.errors.EmptyDataError:
            print(f"警告: 文件 {file_path} 为空, 跳过。")
        except Exception as e:
            print(f"错误: 读取或处理 {file_path} 时出错: {e}")

    # 5. 美化和显示图表
    if not found_data:
        print(f"--- 实例 {instance_name} 未找到任何有效数据, 无法绘图。 ---")
        plt.close()  # 关闭空白的图形窗口
        return

    plt.xlabel('Time')
    # Y轴标签更新
    plt.ylabel('Best Fitness')
    # 标题更新
    plt.title(f'"{instance_name}" (Best Fitness vs. Time)')
    plt.legend(title='Method')
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    # 确保输出目录存在
    os.makedirs(output_dir, exist_ok=True)

    # 保存图像或显示图像
    output_filename = os.path.join(output_dir, f"plot_best_fitness_{instance_name}.png")
    plt.savefig(output_filename)
    print(f"--- 绘图完成: {instance_name}, 图像已保存至 {output_filename} ---")
    if show_plot:
        plt.show()


def plot_gap_scatter(instance_names, algorithm_names, base_dir='.', output_dir='.', show_plot=False):
    """
    Plots a scatter plot showing the gap (%) of each method relative to the best
    found fitness for each instance, indexed by the number of customers.

    X-axis: Customer Number (extracted from instance name)
    Y-axis: Gap (%) = (Method Fitness - Best Fitness in Instance) / Best Fitness in Instance * 100
    """

    results = []

    print("--- Starting Gap Analysis ---")

    # 1. Collect best fitness for every instance and every method
    for instance in instance_names:
        # Extract customer number using regex: finds digits after '-n'
        match = re.search(r'-n(\d+)-', instance)
        if match:
            customer_num = int(match.group(1))
        else:
            print(f"Warning: Could not extract customer number from {instance}. Skipping.")
            continue

        instance_best_values = {}

        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            if not os.path.isdir(method_dir):
                continue

            # Find matching CSV file
            file_path = None
            for file in os.listdir(method_dir):
                if file.endswith('.csv') and instance in file:
                    file_path = os.path.join(method_dir, file)
                    break

            if file_path:
                try:
                    data = pd.read_csv(
                        file_path,
                        sep='[;,]',
                        header=None,
                        names=['time', 'fitness'],
                        engine='python',
                        on_bad_lines='skip'
                    )
                    if not data.empty:
                        # Best fitness is the minimum value found in the 'fitness' column
                        best_val = pd.to_numeric(data['fitness'], errors='coerce').min()
                        if not pd.isna(best_val):
                            instance_best_values[method] = best_val
                except Exception as e:
                    print(f"Error reading {file_path}: {e}")

        # 2. Calculate Gaps for this instance
        if instance_best_values:
            # The baseline is the minimum fitness found among all methods for this instance
            min_fitness_in_instance = min(instance_best_values.values())

            for method, val in instance_best_values.items():
                gap = ((val - min_fitness_in_instance) / min_fitness_in_instance) * 100
                results.append({
                    'customer_num': customer_num,
                    'method': method,
                    'gap': gap,
                    'instance': instance
                })

    if not results:
        print("No valid data found to plot gaps.")
        return

    # 3. Process data for plotting
    df = pd.DataFrame(results)
    # Sort by customer number for a logical X-axis flow
    df = df.sort_values(by='customer_num')

    plt.figure(figsize=(12, 7))

    # 4. Plotting
    # Group by method so each algorithm gets its own color/legend entry
    for method in algorithm_names:
        method_df = df[df['method'] == method]
        if not method_df.empty:
            plt.scatter(
                method_df['customer_num'],
                method_df['gap'],
                label=method,
                alpha=0.7,
                edgecolors='w',
                s=60
            )

    plt.xlabel('Number of Customers')
    plt.ylabel('Gap (%)')
    plt.title('Algorithm Gap Analysis by Instance Scale')
    plt.legend(title='Method')
    plt.grid(True, linestyle='--', alpha=0.5)

    # Ensure Y-axis starts at 0 or slightly below for clarity
    plt.ylim(bottom=-0.5)

    # 5. Save and Show
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'gap_analysis_scatter.png')
    plt.savefig(output_path)
    print(f"--- Gap analysis complete. Plot saved to {output_path} ---")

    if show_plot:
        plt.show()


def plot_gap_scatter_from_sol(instance_names, algorithm_names, base_dir='.', output_dir='.', show_plot=False,
                              point_size=60, point_alpha=0.7):
    """
    绘制基于 .sol 文件中最终 Cost 的 Gap 散点图。

    参数:
    instance_names (list): 实例名称列表 (如 ['CVRP-n100-k10', ...])
    algorithm_names (list): 算法名称列表
    base_dir (str): 数据根目录
    output_dir (str): 图片保存目录
    show_plot (bool): 是否在运行后直接显示图片
    point_size (int): 散点大小 (默认 60)
    point_alpha (float): 散点透明度 (0.0 - 1.0, 默认 0.7)
    """

    results = []

    print("--- 开始绘制 Gap 分析 (基于 .sol 文件) ---")

    # 1. 遍历所有实例
    for instance in instance_names:
        # 尝试从实例名中提取客户数量 (假设格式包含 -n数字-)
        match = re.search(r'-n(\d+)-', instance)
        if match:
            customer_num = int(match.group(1))
        else:
            print(f"警告: 无法从实例名 {instance} 中提取客户数量，跳过此实例。")
            continue

        instance_best_values = {}

        # 2. 遍历该实例下的所有算法目录
        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            if not os.path.isdir(method_dir):
                continue

            # 查找匹配的 .sol 文件
            file_path = None
            if os.path.exists(method_dir):
                for file in os.listdir(method_dir):
                    if file.endswith('.sol') and instance in file:
                        file_path = os.path.join(method_dir, file)
                        break

            # 读取 .sol 文件并解析 Cost
            if file_path:
                try:
                    fitness_val = None
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 倒序查找，因为结果通常在最后
                        for line in reversed(lines):
                            if line.strip().startswith("Cost"):
                                # 假设格式为 "Cost 1234.56"
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    fitness_val = float(parts[1])
                                    break

                    if fitness_val is not None:
                        instance_best_values[method] = fitness_val
                    else:
                        print(f"警告: {file_path} 中未找到 'Cost' 行。")

                except Exception as e:
                    print(f"错误: 读取 {file_path} 时发生异常: {e}")

        # 3. 计算 Gap (相对百分比误差)
        if instance_best_values:
            # 找出当前实例在所有算法中的最小值 (Best Known)
            min_fitness_in_instance = min(instance_best_values.values())

            for method, val in instance_best_values.items():
                if min_fitness_in_instance == 0:
                    gap = 0.0
                else:
                    gap = ((val - min_fitness_in_instance) / min_fitness_in_instance) * 100

                results.append({
                    'customer_num': customer_num,
                    'method': method,
                    'gap': gap,
                    'instance': instance
                })

    # 4. 绘图准备
    if not results:
        print("未找到有效数据，无法绘制 Gap 图。")
        return

    df = pd.DataFrame(results)
    # 按客户数量排序 X 轴
    df = df.sort_values(by='customer_num')

    plt.figure(figsize=(12, 7))

    # 5. 绘制散点图
    for method in algorithm_names:
        method_df = df[df['method'] == method]
        if not method_df.empty:
            plt.scatter(
                method_df['customer_num'],
                method_df['gap'],
                label=method,
                s=point_size,  # 使用自定义大小
                alpha=point_alpha,  # 使用自定义透明度
                edgecolors='w',  # 白色边缘增加对比度
                linewidths=0.8
            )

    plt.xlabel('Number of Customers')
    plt.ylabel('Gap (%)')
    plt.title('Algorithm Gap Analysis by Instance Scale (.sol Files)')
    plt.legend(title='Method')
    plt.grid(True, linestyle='--', alpha=0.5)

    # 为了美观，让 Y 轴稍微往下延伸一点点
    plt.ylim(bottom=-0.5)

    # 6. 保存输出
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, 'gap_analysis_scatter_sol.png')
    plt.savefig(output_path, dpi=300)  # dpi=300 提高保存清晰度
    print(f"--- Gap 分析完成. 图像已保存至 {output_path} ---")

    if show_plot:
        plt.show()


def get_rank_statistics(instance_names, algorithm_names, base_dir='.', output_csv=None):
    """
    统计每个算法在所有实例中获得各名次的次数。

    微调更新:
    - 区分 'Strict Rank 1' (该实例唯一的第1名) 和 'Tied Rank 1' (并列第1名)。
    - 其他名次 (Rank 2, Rank 3...) 保持原样。
    """

    print("--- 开始统计算法排名情况 (区分 Strict/Tied Rank 1) ---")

    raw_data = []

    # 1. 数据收集 (保持原逻辑不变)
    for instance in instance_names:
        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            if not os.path.isdir(method_dir):
                continue

            file_path = None
            if os.path.exists(method_dir):
                for file in os.listdir(method_dir):
                    if file.endswith('.sol') and instance in file:
                        file_path = os.path.join(method_dir, file)
                        break

            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        for line in reversed(lines):
                            if line.strip().startswith("Cost"):
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    fitness = float(parts[1])
                                    raw_data.append({
                                        'Instance': instance,
                                        'Method': method,
                                        'Fitness': fitness
                                    })
                                    break
                except Exception:
                    pass

    if not raw_data:
        print("未找到有效数据。")
        return pd.DataFrame()

    # 2. 转换为 DataFrame
    df_raw = pd.DataFrame(raw_data)

    # 3. 计算基础排名 (Dense Rank)
    # method='dense': 100, 100, 110 -> Rank 1, 1, 2
    df_raw['Rank'] = df_raw.groupby('Instance')['Fitness'].rank(method='dense', ascending=True).astype(int)

    # --- 新增逻辑: 区分 Strict 和 Tied Rank 1 ---

    # 3.1 统计每个实例中有多少个 Rank 1
    # 筛选出Rank为1的行，按实例分组计数
    rank1_counts = df_raw[df_raw['Rank'] == 1].groupby('Instance')['Method'].count()

    # 3.2 定义生成标签的函数
    def get_rank_label(row):
        rank = row['Rank']
        instance = row['Instance']

        if rank == 1:
            # 查一下当前实例有几个第1名
            # 如果字典中找不到(理论不可能)，默认给0
            count = rank1_counts.get(instance, 0)
            if count == 1:
                return "Strict Rank 1"  # 唯一的第1
            else:
                return "Tied Rank 1"  # 并列的第1
        else:
            return f"Rank {rank}"  # 其他名次，如 "Rank 2"

    # 3.3 应用标签
    df_raw['Rank_Label'] = df_raw.apply(get_rank_label, axis=1)

    # 4. 生成交叉表 (Crosstab)
    # 使用新的 Rank_Label 作为列
    rank_table = pd.crosstab(df_raw['Method'], df_raw['Rank_Label'])

    # 5. 美化表格 (列排序)
    # 默认的列排序是字母顺序，会导致 "Rank 10" 排在 "Rank 2" 前面，且 Strict/Tied 位置乱
    # 我们需要自定义排序: Strict 1 -> Tied 1 -> Rank 2 -> Rank 3 ...

    current_cols = rank_table.columns.tolist()

    # 分离出特殊列和普通Rank列
    special_cols = []
    if 'Strict Rank 1' in current_cols: special_cols.append('Strict Rank 1')
    if 'Tied Rank 1' in current_cols: special_cols.append('Tied Rank 1')

    # 提取剩余的 "Rank X" 列并按数字排序
    other_cols = [c for c in current_cols if c not in special_cols]
    # 提取字符串中的数字进行排序 (防止 Rank 10 排在 Rank 2 前面)
    other_cols.sort(key=lambda x: int(x.split()[-1]) if x.split()[-1].isdigit() else 999)

    # 组合最终列顺序
    final_cols = special_cols + other_cols
    rank_table = rank_table[final_cols]

    # 6. 保存或打印
    print("\n--- 排名统计表 (Rank Statistics) ---")
    print(rank_table)

    if output_csv:
        rank_table.to_csv(output_csv)
        print(f"表格已保存至: {output_csv}")

    return rank_table
def get_average_gap_statistics(instance_names, algorithm_names, base_dir='.', output_csv=None, baseline=None):
    """
    计算每个算法在所有实例上的平均 Gap (%)。

    逻辑：
    1. 遍历每个实例，读取所有算法的 Cost。
    2. 确定基准值 (Reference Value):
       - 如果 baseline 为 None: 取当前实例所有算法中的最小值 (Best Found)。
       - 如果 baseline 为 str: 取对应算法在该实例下的 Cost。
       - 如果 baseline 为 dict: 取 dict[instance_name] 的值。
    3. 计算每个算法的 Gap = (Cost - Reference) / Reference * 100。
    4. 统计平均值。

    参数:
    baseline (str or dict, optional):
        - str: 指定某个算法名称作为基准 (需在 algorithm_names 中)。
        - dict: {instance_name: cost} 指定每个实例的已知最优解。
        - None: 默认模式，使用当前对比组中的最小值作为基准。
    """
    print(f"--- 开始计算平均 Gap (基于 .sol 文件) | Baseline模式: {baseline if baseline else 'Best Found'} ---")

    gap_data = []

    # 1. 遍历所有实例
    for instance in instance_names:
        instance_costs = {}

        # 2. 读取该实例下所有算法的 Cost
        for method in algorithm_names:
            method_dir = os.path.join(base_dir, method)
            file_path = None

            # 查找 .sol 文件
            if os.path.isdir(method_dir):
                for file in os.listdir(method_dir):
                    if file.endswith('.sol') and instance in file:
                        file_path = os.path.join(method_dir, file)
                        break

            # 解析 Cost
            if file_path:
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                        # 倒序查找 Cost，防止文件头有干扰信息
                        for line in reversed(lines):
                            if line.strip().startswith("Cost"):
                                parts = line.strip().split()
                                if len(parts) >= 2:
                                    instance_costs[method] = float(parts[1])
                                    break
                except Exception:
                    pass

        # 3. 确定基准值 (Base Value)
        if not instance_costs:
            continue

        base_val = None

        # --- 新增逻辑: 确定 Base Value ---
        if baseline is None:
            # 默认逻辑: 取当前发现的最小值
            base_val = min(instance_costs.values())

        elif isinstance(baseline, str):
            # 模式: 指定某个算法作为基准
            if baseline in instance_costs:
                base_val = instance_costs[baseline]
            else:
                # 如果当前实例下，基准算法没有解，则跳过该实例的统计，或者您也可以选择报错
                # print(f"警告: 实例 {instance} 缺少基准算法 {baseline} 的结果，跳过。")
                continue

        elif isinstance(baseline, dict):
            # 模式: 传入了外部的 BKS 字典
            base_val = baseline.get(instance)
            if base_val is None:
                continue

        # 4. 计算当前实例的 Gap
        # 必须确保 base_val 有效且不为 0 (防止除以0错误)
        if base_val is not None:
            for method, cost in instance_costs.items():
                if base_val == 0:
                    # 如果基准值为0，且cost也是0，gap为0；否则无法计算(无穷大)
                    gap = 0.0 if cost == 0 else np.inf
                else:
                    # 公式: (Cost - Base) / Base * 100
                    gap = ((cost - base_val) / base_val) * 100

                gap_data.append({
                    'Method': method,
                    'Gap': gap,
                    'Instance': instance
                })

    if not gap_data:
        print("未找到有效数据或无法建立基准。")
        return pd.DataFrame()

    # 5. 汇总计算平均值
    df_gaps = pd.DataFrame(gap_data)

    # 按方法分组，计算 Gap 的平均值
    df_avg = df_gaps.groupby('Method')['Gap'].mean().reset_index()
    df_avg.rename(columns={'Gap': 'Average Gap (%)'}, inplace=True)

    # 按平均 Gap 从小到大排序
    df_avg = df_avg.sort_values(by='Average Gap (%)')

    # 6. 输出结果
    print("\n--- 平均 Gap 统计表 ---")
    print(df_avg)

    if output_csv:
        df_avg.to_csv(output_csv, index=False)
        print(f"统计表已保存至: {output_csv}")

    return df_avg