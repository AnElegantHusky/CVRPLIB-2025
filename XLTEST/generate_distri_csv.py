import os
import csv
import re


def parse_script_file(script_filename):
    """
    解析 shell 脚本文件，提取参数。
    返回一个字典，Key 为预期的文件名中的 n (即 script_n + 1)，Value 为参数字典。
    """
    params_map = {}

    try:
        with open(script_filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        print(f"正在解析 {script_filename} ...")
        for line in lines:
            line = line.strip()
            if not line or not line.startswith("python"):
                continue

            # 分割命令行参数
            parts = line.split()
            # 格式: python generatorLarge.py [n] [depot] [cust] [demand] [route] [seed]
            # 索引: 0      1                2    3       4      5        6       7

            if len(parts) >= 8:
                script_n = int(parts[2])

                # 规则：文件名中的 n = 脚本中的 n + 1
                # 例如：脚本里是 1047，对应文件名里的 n1048
                file_n = script_n + 1

                params_map[file_n] = {
                    'script_n': script_n,
                    'depot_pos': parts[3],
                    'cust_pos': parts[4],
                    'demand_dist': parts[5],
                    'route_size': parts[6],
                    'seed': parts[7]
                }
        return params_map

    except FileNotFoundError:
        print(f"❌ 错误：在当前目录下找不到 {script_filename} 文件。")
        return {}


def generate_csv(directory, script_data):
    """
    扫描目录下的 vrp 文件，匹配参数并生成 CSV。
    """
    output_file = '../plot/instance_params.csv'
    # CSV 表头
    headers = [
        'Instance File Name',
        'n (from file)',
        'k (Vehicles)',
        'n (raw script arg)',
        'Depot Positioning',
        'Customer Positioning',
        'Demand Distribution',
        'Average Route Size',
        'Seed'
    ]

    rows = []
    files = os.listdir(directory)
    matched_count = 0

    print(f"正在扫描文件夹: {directory} ...")

    # 正则表达式匹配文件名: XLTEST-n{数字}-k{数字}.vrp
    # 注意：根据通常的命名习惯，可能是 XL-n... 或 XLTEST-n...，这里适配 XLTEST
    pattern = re.compile(r'XLTEST-n(\d+)-k(\d+)\.vrp')

    for filename in files:
        if not filename.endswith('.vrp'):
            continue

        match = pattern.search(filename)
        if match:
            file_n = int(match.group(1))
            k_value = int(match.group(2))

            # 在脚本数据中查找对应的参数
            if file_n in script_data:
                p = script_data[file_n]
                row = [
                    filename,
                    file_n,
                    k_value,
                    p['script_n'],
                    p['depot_pos'],
                    p['cust_pos'],
                    p['demand_dist'],
                    p['route_size'],
                    p['seed']
                ]
                rows.append(row)
                matched_count += 1
            else:
                print(f"⚠️ 警告: 找到文件 {filename} (n={file_n})，但在脚本中没有找到对应参数 (期望脚本 n={file_n - 1})")

    # 按 n 的大小排序
    rows.sort(key=lambda x: x[1])

    # 写入 CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(rows)

    print("-" * 30)
    print(f"🎉 成功生成 CSV 文件: {output_file}")
    print(f"共匹配到 {matched_count} 个实例。")


if __name__ == "__main__":
    # 设置当前目录
    current_dir = os.getcwd()
    script_name = "genXLTEST.sh"

    # 1. 获取映射数据
    data_map = parse_script_file(os.path.join(current_dir, script_name))

    if data_map:
        # 2. 扫描文件并生成表格
        generate_csv(current_dir, data_map)