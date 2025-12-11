import pandas as pd
import matplotlib.pyplot as plt
import os
from pathlib import Path

def plot_csv(file_path, instance_name, setting, save_path):
    color_dict = {
        'sisr': 'black',
        'ails2': 'blue',
        'filo2': 'red',
    }


    df = pd.read_csv(file_path)
    # --- 1. 读取 CSV 文件 ---
    # 将 'data.csv' 替换为你的实际文件名
    # 如果文件在其他路径，请填写完整路径，例如: r'C:\Users\Name\Desktop\data.csv'
    try:
        df = pd.read_csv(file_path)
    except FileNotFoundError:
        print("错误：找不到文件，请检查文件名和路径是否正确。")
        exit()

    # --- 2. 开始绘图 ---
    # 设置画布大小（宽10，高6）
    plt.figure(figsize=(10, 6))

    # 获取数据中所有唯一的算法名称（例如：['sisr', 'filo2', 'ails2']）
    algorithms = df['algo_name'].unique()
    algorithms = algorithms[algorithms != 'sisr']

    # 循环遍历每一个算法，单独为它画一条线
    for algo in algorithms:
        # 2.1 筛选数据：只取出当前算法及其对应的 score 和 runningtime
        subset = df[df['algo_name'] == algo]

        # 2.2 关键步骤：按时间先后排序
        # 确保画线时是按时间顺序连接点的，防止线条乱跑
        subset = subset.sort_values(by='runningtime')

        # 2.3 绘制线条和数据点
        # x轴: runningtime, y轴: score
        # marker='o' 表示在数据点位置画个圆圈标记
        # label=algo 用于自动生成图例
        plt.plot(subset['runningtime'], subset['score'], marker='o', linestyle='-', linewidth=2, label=algo, c=color_dict[algo])

    # --- 3. 图表美化 ---
    plt.title(setting+'  '+instance_name, fontsize=14, fontweight='bold')  # 设置标题
    plt.xlabel('Running Time (seconds)', fontsize=12)  # 设置X轴标签
    plt.ylabel('Score', fontsize=12)  # 设置Y轴标签

    plt.legend(title="Algorithm Name")  # 显示图例，自动识别不同颜色的线代表什么算法
    plt.grid(True, linestyle='--', alpha=0.6)  # 添加网格背景，方便看数

    # 自动调整布局，防止标签显示不全
    plt.tight_layout()

    plt.savefig(save_path / Path(instance_name+ '.png'))

    # 显示图表
    plt.show()

if __name__ == '__main__':
    root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB20251211')

    for root, dirs, files in os.walk(root_path):
        if 'XLTEST' in root:
            instance_name = Path(root).name
            log = Path(root).parent.name
            server = Path(root).parent.parent.name
            setting = None
            save_path = Path(root).resolve().parent
            if 'noah125' == server:
                setting = 'V3.1 5d'
            elif 'noah163' == server:
                setting = 'V3.1 1d'
            if 'log_buffer' != log:
                continue
            for file in files:
                if 'solution_history' in file:
                    file_path = os.path.join(root, file)
                    plot_csv(file_path, instance_name, setting, save_path)
