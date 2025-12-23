import pandas as pd
import matplotlib.pyplot as plt
import os
from pathlib import Path
import pprint

from pymoo.problems.dynamic import df


def plot_csv(file_path, instance_name, setting, save_path):
    color_dict = {
        'HGS-TV': 'green',
        'ails2_etaMax1.000_stoppingTime600.00': 'black',
        'ails2_etaMax1.000_stoppingTime3600.00': 'darkred',
        'ails2_etaMax1.000_stoppingTime7200.00': 'tomato',
        'ails2_etaMax1.000_stoppingTime28800.00': 'orange',
        'ails2_etaMax1.000_stoppingTime14400.00': 'red',
        'sisr': 'gold',
        'ails2_etaMax0.050_stoppingTime86400.00': 'cyan',
        'ails2_etaMax0.010_stoppingTime86400.00': 'blue',
        'ails2_etaMax0.100_stoppingTime86400.00': 'navy',
        'filo2': 'darkviolet',
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
    # algorithms = algorithms[algorithms != 'sisr']

    # 循环遍历每一个算法，单独为它画一条线
    all_best_value = float('inf')
    all_best_algorithm = None
    all_best_running_time = None
    counter_dict = dict()
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
        # plt.plot(subset['runningtime'], subset['score'], marker='o', linestyle='-', linewidth=2, label=algo)
        counter_dict[algo] = sum(subset['runningtime'] > 86400) # after warmup
        if list(subset['score'])[-1] < all_best_value:
            all_best_value = list(subset['score'])[-1]
            all_best_algorithm = algo
            all_best_running_time = subset['runningtime'].iloc[-1]
    print(setting, instance_name, all_best_algorithm, all_best_value, all_best_running_time)

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
    return all_best_algorithm, all_best_value, all_best_running_time, counter_dict

def print_csv(file_path, instance_name, setting):

    df = pd.read_csv(file_path)
    print(setting, instance_name)
    result = dict(zip(df['algo_name'], df['seed_count']))
    return result

if __name__ == '__main__':
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB20251211')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB20251215')
    root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/results1223/results03')

    all_results = dict()
    counter_dict = dict()

    for root, dirs, files in os.walk(root_path):
        if 'XLTEST' in root:
            instance_name = Path(root).name
            log = Path(root).parent.name
            server = Path(root).parent.parent.name
            setting = None
            save_path = Path(root).resolve().parent
            # if 'noah125' == server:
            #     setting = 'V3.2 5d'
            # elif 'noah163' == server:
            #     setting = 'V3.2 1d'
            # if 'log_buffer' != log:
            #     continue
            if '123' in server:
                setting = 'V3.5(HGS) 5d 1h'
            elif '126' in server:
                setting = 'V3.5(HGS) 5d 10min'
            elif '125' in server:
                setting = 'V3.5(HGS) 5d 1min'
            else:
                continue

            for file in files:
                if 'solution_history' in file:
                    if '1h' in setting:
                        continue

                    file_path = os.path.join(root, file)
                    algo, value, running_time, best_counter = plot_csv(file_path, instance_name, setting, save_path)

                    for key in best_counter.keys():
                        if key in counter_dict.keys():
                            counter_dict[key] += best_counter[key]
                        else:
                            counter_dict[key] = best_counter[key]

                    if instance_name in all_results.keys():
                        if all_results[instance_name][2] > value:
                            all_results[instance_name] = [setting, algo, value, running_time]
                    else:
                        all_results[instance_name] = [setting, algo, value, running_time]

                # if 'survivor_stats' in file:
                #     if '1h' in setting:
                #         continue
                #     file_path = os.path.join(root, file)
                #     best_counter = print_csv(file_path, instance_name, setting)
                #     for key in best_counter.keys():
                #         if key in counter_dict.keys():
                #             counter_dict[key] += best_counter[key]
                #         else:
                #             counter_dict[key] = best_counter[key]

    pprint.pprint(counter_dict)
    # pprint.pprint(all_results)