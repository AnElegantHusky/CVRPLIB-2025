import os
import matplotlib.pyplot as plt
import pandas as pd
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