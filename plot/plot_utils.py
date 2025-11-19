import os
import pandas as pd
import matplotlib.pyplot as plt

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