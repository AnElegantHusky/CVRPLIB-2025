import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os
from pathlib import Path
import pprint
from tabulate import tabulate
from pymoo.problems.dynamic import df
import sys
import matplotlib.patches as patches
import re

def plot_csv(file_path, instance_name, setting, save_path):
    # color_dict = {
    #     'HGS-TV': 'green',
    #     # 'ails2_etaMax1.000_stoppingTime600.00': 'black',
    #     # 'ails2_etaMax1.000_stoppingTime3600.00': 'darkred',
    #     # 'ails2_etaMax1.000_stoppingTime7200.00': 'tomato',
    #     # 'ails2_etaMax1.000_stoppingTime28800.00': 'orange',
    #     # 'ails2_etaMax1.000_stoppingTime14400.00': 'red',
    #     'sisr': 'gold',
    #     'ails2_etaMax0.005_stoppingTime86400.00': 'black',
    #     # 'ails2_etaMax0.050_stoppingTime86400.00': 'cyan',
    #     # 'ails2_etaMax0.010_stoppingTime86400.00': 'blue',
    #     # 'ails2_etaMax0.020_stoppingTime86400.00': 'orange',
    #     # 'ails2_etaMax0.100_stoppingTime86400.00': 'navy',
    #     'ails2_etaMax1.000_stoppingTime86400.00': 'navy',
    #     'filo2': 'darkviolet',
    #
    #     'ails2_eoh_omega': 'pink',
    #     'ails2_eoh_acc': 'purple',
    #     'ails2_eoh_acc_large': 'darkred',
    #
    #     'ails2_etaMax1.000_stoppingTime1500.00': 'blue',
    #     'ails2_etaMax1.000_stoppingTime300.00': 'tomato',
    #     'ails2_etaMax1.000_stoppingTime6000.00': 'yellow',
    #     'ails2_etaMax1.000_stoppingTime3000.00': 'red',
    #
    #     'ails2_etaMax0.010_stoppingTime1500.00': 'cyan',
    #     'ails2_etaMax0.005_stoppingTime300.00': 'navy',
    #     'ails2_etaMax0.020_stoppingTime300.00': 'orange',
    # }

    color_dict = {
        # Group 1: 基准/独立算法 (高对比度)
        'HGS-TV': '#333333',  # 深灰色/黑色 (主要基准)
        'filo2': '#FFD700',  # 金色 (Gold) - 与深色背景对比强烈

        # Group 2: EOH 系列 (暖色/紫红系 - 变体梯度)
        'ails2_eoh_omega2': '#FF69B4',  # 热粉色 (HotPink)
        'ails2_eoh_acc': '#C71585',  # 中紫罗兰红 (MediumVioletRed)
        'ails2_eoh_acc_large': '#800080',  # 紫色 (Purple) - 最深

        # Group 3: etaMax=1.0 系列 (蓝色系 - 按时间由短到长渐变)
        # 时间短 -> 颜色浅; 时间长 -> 颜色深
        'ails2_etaMax1.000_stoppingTime86400.00': '#87CEEB',  # 天蓝色 (SkyBlue)
        'ails2_etaMax1.000_stoppingTime432000.00': '#4169E1',  # 皇家蓝 (RoyalBlue)
        'ails2_etaMax1.000_stoppingTime864000.00': '#0000CD',  # 中蓝色 (MediumBlue)
        'ails2_etaMax1.000_stoppingTime1728000.00': '#000080',  # 海军蓝 (Navy)

        # Group 4: 低 etaMax 系列 (绿色系 - 按 etaMax 值由小到大渐变)
        # 参数小 -> 颜色浅; 参数大 -> 颜色深
        'ails2_etaMax0.005_stoppingTime86400.00': '#90EE90',  # 淡绿色 (LightGreen)
        'ails2_etaMax0.010_stoppingTime432000.00': '#228B22',  # 森林绿 (ForestGreen)
        'ails2_etaMax0.020_stoppingTime86400.00': '#006400',  # 深绿色 (DarkGreen)
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

    plt.figure(figsize=(10, 6))
    algorithms = df['algo_name'].unique()

    all_best_value = float('inf')
    all_best_algorithm = None
    all_best_running_time = None
    counter_dict = dict()


    for algo in algorithms:
        subset = df[df['algo_name'] == algo]
        subset = subset.sort_values(by='runningtime')

        if 'ails2_etaMax1.000' in algo:
            sec = float(re.findall(r"\d+(?:\.\d+)?", algo)[2])
            day = int(sec // 86400)

            plt.plot(subset['runningtime'], subset['score'], marker='o', linestyle='-', linewidth=2,
                     label=f'ails2_external_{day}day',
                     c=color_dict[algo])
            # print(save_path, (running_time_np[1:]-running_time_np[:-1])/60)
        else:
            plt.plot(subset['runningtime'], subset['score'], marker='o', linestyle='-', linewidth=2,
                     label=algo, c=color_dict[algo])
        # plt.plot(subset['runningtime'], subset['score'], marker='o', linestyle='-', linewidth=2, label=algo)
        # counter_dict[algo] = sum(subset['runningtime'] > 3600) # after warmup
        counter_dict[algo] = sum(subset['runningtime'] > 86400) # after 1 day
        if list(subset['score'])[-1] < all_best_value:
            all_best_value = list(subset['score'])[-1]
            all_best_algorithm = algo
            all_best_running_time = subset['runningtime'].iloc[-1]
    # print(setting, instance_name, all_best_algorithm, all_best_value, all_best_running_time)

    # --- 3. 图表美化 ---
    plt.title(setting+'  '+instance_name, fontsize=14, fontweight='bold')  # 设置标题
    plt.xlabel('Running Time (seconds)', fontsize=12)  # 设置X轴标签
    plt.ylabel('Score', fontsize=12)  # 设置Y轴标签

    handles, labels = plt.gca().get_legend_handles_labels()
    order = sorted(zip(labels, handles))
    labels_sorted, handles_sorted = zip(*order)
    plt.legend(handles_sorted, labels_sorted, title="Algorithm Name", loc='upper right')

    # # plt.xticks(np.arange(300, 1800, 120))
    # plt.legend(title="Algorithm Name")  # 显示图例，自动识别不同颜色的线代表什么算法
    plt.grid(True, linestyle='--', alpha=0.6)  # 添加网格背景，方便看数

    # 自动调整布局，防止标签显示不全
    plt.tight_layout()

    plt.savefig(save_path / Path(instance_name+ '.png'))

    # 显示图表
    plt.show()
    return all_best_algorithm, all_best_value, all_best_running_time, counter_dict


def extract_and_format(text):
    # 1. 使用正则提取所有数值
    numbers = re.findall(r"\d+(?:\.\d+)?", text)
    # 此时 numbers = ['2', '1.000', '3600.00']

    # 确保至少有两个数字，否则直接返回原文本防止报错
    if len(numbers) < 2:
        return text

    # 2. 截取列表的最后两个元素
    last_two = numbers[-2:]
    # 此时 last_two = ['1.000', '3600.00']

    # 3. 处理最后一个元素：按 '.' 分割并取第一部分（即去除小数）
    last_two[-1] = last_two[-1].split('.')[0]
    # 此时 last_two = ['1.000', '3600']

    # 4. 用下划线连接
    return "_".join(last_two)

def plot_improvement(file_path, instance_name, setting, save_path):
    # color_dict = {
    #     'HGS-TV': 'green',
    #     # 'ails2_etaMax1.000_stoppingTime600.00': 'black',
    #     'ails2_etaMax1.000_stoppingTime3600.00': 'darkred',
    #     'ails2_etaMax1.000_stoppingTime7200.00': 'tomato',
    #     # 'ails2_etaMax1.000_stoppingTime28800.00': 'orange',
    #     'ails2_etaMax1.000_stoppingTime14400.00': 'red',
    #     'sisr': 'gold',
    #     'ails2_etaMax0.005_stoppingTime86400.00': 'black',
    #     'ails2_etaMax0.050_stoppingTime86400.00': 'cyan',
    #     'ails2_etaMax0.010_stoppingTime86400.00': 'blue',
    #     'ails2_etaMax0.020_stoppingTime86400.00': 'orange',
    #     # 'ails2_etaMax0.100_stoppingTime86400.00': 'navy',
    #     'ails2_etaMax1.000_stoppingTime86400.00': 'navy',
    #     'filo2': 'darkviolet',
    #
    #     'ails2_eoh_omega': 'pink',
    #     'ails2_eoh_acc': 'purple',
    # }

    color_dict = {
        # Group 1: 基准/独立算法 (高对比度)
        'HGS-TV': '#333333',  # 深灰色/黑色 (主要基准)
        'filo2': '#FFD700',  # 金色 (Gold) - 与深色背景对比强烈

        # Group 2: EOH 系列 (暖色/紫红系 - 变体梯度)
        'ails2_eoh_omega2': '#FF69B4',  # 热粉色 (HotPink)
        'ails2_eoh_acc': '#C71585',  # 中紫罗兰红 (MediumVioletRed)
        'ails2_eoh_acc_large': '#800080',  # 紫色 (Purple) - 最深

        # Group 3: etaMax=1.0 系列 (蓝色系 - 按时间由短到长渐变)
        # 时间短 -> 颜色浅; 时间长 -> 颜色深
        'ails2_etaMax1.000_stoppingTime86400.00': '#87CEEB',  # 天蓝色 (SkyBlue)
        'ails2_etaMax1.000_stoppingTime432000.00': '#4169E1',  # 皇家蓝 (RoyalBlue)
        'ails2_etaMax1.000_stoppingTime864000.00': '#0000CD',  # 中蓝色 (MediumBlue)
        'ails2_etaMax1.000_stoppingTime1728000.00': '#000080',  # 海军蓝 (Navy)

        # Group 4: 低 etaMax 系列 (绿色系 - 按 etaMax 值由小到大渐变)
        # 参数小 -> 颜色浅; 参数大 -> 颜色深
        'ails2_etaMax0.005_stoppingTime86400.00': '#90EE90',  # 淡绿色 (LightGreen)
        'ails2_etaMax0.010_stoppingTime432000.00': '#228B22',  # 森林绿 (ForestGreen)
        'ails2_etaMax0.020_stoppingTime86400.00': '#006400',  # 深绿色 (DarkGreen)
    }

    df = pd.read_csv(file_path)



    # 创建画布
    fig, ax = plt.subplots(figsize=(12, 8))

    # ==========================================
    # 核心逻辑修改：数据分组 (Merging Logic)
    # ==========================================

    # 1. 将连续相同的 seed_algo 归为一组
    groups = []
    if not df.empty:
        current_group = [df.iloc[0]]

        for i in range(1, len(df)):
            row = df.iloc[i]
            prev_row = df.iloc[i-1]

            # 如果当前行的算法与前一行相同，加入当前组
            if row['seed_algo'] == prev_row['seed_algo']:
                current_group.append(row)
            else:
                # 否则，封存当前组，开启新组
                groups.append(current_group)
                current_group = [row]

        # 不要忘记添加最后一组
        if current_group:
            groups.append(current_group)

    # ==========================================
    # 绘图循环 (遍历组而不是行)
    # ==========================================

    prev_time = 0 # 初始时间
    added_labels = set() # 用于图例去重

    for group in groups:
        # group 是一个包含多个 Series(行) 的列表
        first_row = group[0]
        last_row = group[-1]

        algo_name_raw = first_row['seed_algo']

        # --- 计算合并后的坐标参数 ---

        # 结束时间：这一组最后一行的记录时间
        curr_time = last_row['recording_time']

        # 种子分数 (矩形顶部)：这一组第一行的开始分数
        seed_score = first_row['seed_score']

        # 胜者分数 (矩形底部)：这一组最后一行的结束分数
        winner_score = last_row['winner_score']

        # 总提升：这一组所有 improvement 的和
        # 也可以直接用 seed_score - winner_score 计算，结果是一样的
        total_improvement = sum(item['improvement'] for item in group)

        # 计算矩形几何参数
        width = curr_time - prev_time
        height = seed_score - winner_score

        # 矩形左下角坐标 (x, y) = (开始时间, 底部胜者分数)
        # 注意：matplotlib Rectangle 是从左下角画起的
        xy = (prev_time, winner_score)

        # 获取颜色，如果没有定义则默认为灰色
        color = color_dict.get(algo_name_raw, 'grey')

        # 处理图例标签 (仅在第一次出现时添加 label，防止图例重复)
        label_for_legend = None
        if algo_name_raw not in added_labels:
            label_for_legend = algo_name_raw
            added_labels.add(algo_name_raw)

        # --- 绘制矩形 ---
        rect = patches.Rectangle(
            xy,
            width,
            height,
            linewidth=1,
            edgecolor='white', # 加个白边区分不同组
            facecolor=color,
            alpha=0.6,
            label=label_for_legend # 这里添加label用于自动生成图例
        )
        ax.add_patch(rect)

        # --- 处理显示名称 (你的字符串处理逻辑) ---
        name = algo_name_raw
        if 'ails2_etaMax1.000' in name:
            sec = float(re.findall(r"\d+(?:\.\d+)?", name)[2])
            day = int(sec // 86400)
            name = f'ails2_external_{day}day'

        if 'ails2_eta' in name:
            name = extract_and_format(name)
        elif 'ails2_eoh' in name:
            name = name.replace('ails2_eoh_', '')

        # --- 添加文字标注 ---
        # 只有当矩形足够大时才显示，避免文字重叠太乱 (可选优化)
        if width > 0 and height > 0:
            label_text = f"{name}: {int(total_improvement)}" # 换行显示更清晰

            center_x = prev_time + width / 2
            center_y = winner_score + height / 2

            ax.text(
                center_x,
                center_y,
                label_text,
                ha='center',
                va='center',
                fontsize=8,
                color='black',
                fontweight='normal' # 如果觉得字体太粗可以改 normal
            )

        # --- 更新时间游标 ---
        prev_time = curr_time

    # ==========================================
    # 设置图表细节
    # ==========================================

    ax.set_xlim(0, df['recording_time'].max() * 1.05)
    ax.set_ylim(df['winner_score'].min() - 50, df['seed_score'].max() + 50)

    plt.title(setting + '  ' + instance_name, fontsize=14, fontweight='bold')
    plt.xlabel('Running Time (seconds)', fontsize=12)
    plt.ylabel('Score', fontsize=12)

    handles, labels = plt.gca().get_legend_handles_labels()
    order = sorted(zip(labels, handles))
    labels_sorted, handles_sorted = zip(*order)
    plt.legend(handles_sorted, labels_sorted, title="Algorithm Name", loc='upper right')

    # 自动生成的图例 (基于 rect 的 label 参数)
    # plt.legend(title="Algorithm Name", loc='upper right')
    # plt.xticks(np.arange(300, 1800, 120))
    plt.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    # 确保保存路径存在
    save_dir = Path(save_path)
    save_dir.mkdir(parents=True, exist_ok=True)

    plt.savefig(save_dir / f'improve_{instance_name}.png')

    plt.show()


def print_csv(file_path, instance_name, setting):
    df = pd.read_csv(file_path)
    # print(setting, instance_name) # 注释掉以减少刷屏
    result = dict(zip(df['algo_name'], df['seed_count']))
    return result

if __name__ == '__main__':
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB20251211')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB20251215')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/results1223/results03')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB2025-251229')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/CVRPLIB2025-260104')
    # root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/log_csv_202601120805')
    root_path = Path('E:/onedrive/cityU/CVRPLIB/all_in_one/20260114_172818')

    final_best_list = []
    final_stats_list = []

    all_results = dict()
    counter_dict = dict()
    setting = None
    for root, dirs, files in os.walk(root_path):
        # if 'XLTEST' in root:
        if 'XL' in root:
            instance_name = Path(root).name
            log = Path(root).parent.name
            server = Path(root).parent.parent.name
            save_path = Path(root).resolve().parent
            # if 'noah125' == server:
            #     setting = 'V3.2 5d'
            # elif 'noah163' == server:
            #     setting = 'V3.2 1d'
            # if 'log_buffer' != log:
            #     continue
            # if '123' in server:
            #     setting = 'V3.5(HGS) 5d 1h'
            # elif '126' in server:
            #     setting = 'V3.5(HGS) 5d 10min'
            # elif '125' in server:
            #     setting = 'V3.5(HGS) 5d 1min'
            # else:
            #     continue

            # if '123' in server:
            #     setting = 'V3.5.5 5d 1h'
            # elif '126' in server:
            #     setting = 'V3.5.5 5d 1min'
            # elif '125' in server:
            #     setting = 'V3.5.5(HGS) 5d 1h'
            # else:
            #     continue

            # if '126' in server:
            #     setting = 'V4.0 5d 1h'
            # elif '125' in server:
            #     setting = 'V4.0 5d 10min'
            # else:
            #     continue

            # if '125' in server:
            #     setting = 'V final test 30min 2min'
            # else:
            #     continue

            if '126' in server:
                setting = 'Final '
            else:
                continue

            for file in files:
                if 'solution_history' in file:
                    # if '1h' in setting:
                    #     continue

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

                if 'survivor_stats' in file:
                    # if '1h' in setting:
                    #     continue
                    file_path = os.path.join(root, file)
                    best_counter = print_csv(file_path, instance_name, setting)
                    for key in best_counter.keys():
                        if key in counter_dict.keys():
                            counter_dict[key] += best_counter[key]
                        else:
                            counter_dict[key] = best_counter[key]
            # print('='*20, setting, '='*20, )
            # pprint.pprint(counter_dict)
            # # print(tabulate(counter_dict, headers="keys", tablefmt="fancy_grid"))
            # # pprint.pprint(all_results)
            # print(tabulate(all_results, headers="keys", tablefmt="fancy_grid"))
            # all_results = dict()
            # counter_dict = dict()
                if 'improvement_stats' in file:
                    file_path = os.path.join(root, file)
                    plot_improvement(file_path, instance_name, setting, save_path)

            if instance_name in all_results:
                data = all_results[instance_name]
                final_best_list.append({
                    "Instance": instance_name,
                    "Setting": data[0],
                    "Best_Algo": data[1],
                    "Score": data[2],
                    "Time_s": data[3]
                })

            for algo, count in counter_dict.items():
                final_stats_list.append({
                    "Instance": instance_name,
                    "Setting": setting,
                    "Algorithm": algo,
                    "Count": count
                })

            all_results = dict()
            counter_dict = dict()

    print("\nTABLE_1_BEST_RESULTS_ALL_SETTINGS")
    if final_best_list:
        df_best = pd.DataFrame(final_best_list)
        # 按 Instance 排序，方便对比不同 Setting 下同一个 Instance 的区别
        df_best = df_best.sort_values(by=['Instance', 'Setting'])
        # 输出为 CSV 格式 (sys.stdout 直接打印)
        df_best.to_csv(sys.stdout, index=False)

    # 2. 输出统计次数合并表
    print("\nTABLE_2_STATISTICS_ALL_SETTINGS")
    if final_stats_list:
        df_stats = pd.DataFrame(final_stats_list)

        # 创建透视表：
        # 行索引：Instance 和 Setting
        # 列索引：各种算法名称
        # 值：Count
        pivot_stats = df_stats.pivot_table(
            index=['Instance', 'Setting'],
            columns='Algorithm',
            values='Count',
            aggfunc='sum'
        ).fillna(0).astype(int)

        # 输出为 CSV 格式
        pivot_stats.to_csv(sys.stdout)