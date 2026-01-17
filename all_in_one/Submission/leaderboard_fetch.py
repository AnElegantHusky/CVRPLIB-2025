import requests
from bs4 import BeautifulSoup
import os
import glob


def get_cvrplib_instances_float():
    """
    爬取 CVRPLIB 数据并将第三列的金额/数值转换为浮点数。
    针对格式: "$380{,}211.00" -> 380211.0
    """
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    print("正在连接 CVRPLIB 获取最新榜单...")
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 定位表格 (增加了更通用的定位方式)
        table = soup.select_one('main section table')
        if not table:
            table = soup.find('table')

        if not table:
            print("未找到表格数据。")
            return {}

        data_dict = {}
        tbody = table.find('tbody')

        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')

                if len(cols) >= 3:
                    # 获取 Instance Name (通常在第1列)
                    key = cols[0].get_text(strip=True)
                    # 获取 BKS Value (通常在第3列)
                    raw_value = cols[2].get_text(strip=True)

                    try:
                        # 数据清洗: 去除 $, ,, {, }
                        clean_value = raw_value.replace('$', '').replace(',', '').replace('{', '').replace('}', '')
                        float_value = float(clean_value)
                        data_dict[key] = float_value
                    except ValueError:
                        continue

        print(f"榜单获取成功，共包含 {len(data_dict)} 个实例的数据。")
        return data_dict

    except Exception as e:
        print(f"爬取发生错误: {e}")
        return {}


def read_local_fitness(file_path):
    """
    读取 .sol 文件并解析 fitness。
    规则：读取最后一个非空行，格式预期为 'Cost {fitness}'
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f.readlines() if line.strip()]

        if not lines:
            return None

        last_line = lines[-1]
        # 简单校验格式是否包含 'Cost'
        if "Cost" in last_line:
            # 分割字符串获取最后一个部分，例如 "Cost 12345" -> 12345
            parts = last_line.split()
            fitness_str = parts[-1]
            return float(fitness_str)
        else:
            print(f"格式警告 [{os.path.basename(file_path)}]: 最后一行不是 'Cost X' 格式 -> '{last_line}'")
            return None

    except Exception as e:
        print(f"读取错误 [{os.path.basename(file_path)}]: {e}")
        return None


def filter_solutions_by_leaderboard(leaderboard_data, sol_folder="to_sub_sols"):
    """
    过滤文件夹中的解：只保留比 leaderboard 更好的解。
    """
    if not os.path.exists(sol_folder):
        print(f"文件夹 '{sol_folder}' 不存在。")
        return

    # 获取所有 .sol 文件
    sol_files = glob.glob(os.path.join(sol_folder, "*.sol"))

    if not sol_files:
        print(f"'{sol_folder}' 文件夹下没有找到 .sol 文件。")
        return

    print(f"\n开始检查 {len(sol_files)} 个本地文件...")
    print("-" * 60)
    print(f"{'Instance':<25} | {'Local':<12} | {'BKS (Web)':<12} | {'Action'}")
    print("-" * 60)

    kept_count = 0
    removed_count = 0

    for file_path in sol_files:
        file_name = os.path.basename(file_path)
        instance_name = os.path.splitext(file_name)[0]  # 去除 .sol 后缀作为 key

        local_fitness = read_local_fitness(file_path)

        # 1. 如果本地文件无法解析，建议跳过（安全起见不删除）
        if local_fitness is None:
            print(f"{instance_name:<25} | {'ERROR':<12} | {'N/A':<12} | SKIP (Parse Error)")
            continue

        # 2. 检查该实例是否在榜单中
        if instance_name not in leaderboard_data:
            print(f"{instance_name:<25} | {local_fitness:<12} | {'Not Found':<12} | KEEP (New Instance)")
            kept_count += 1
            continue

        bks_fitness = leaderboard_data[instance_name]

        # 3. 核心比较逻辑
        # 浮点数比较通常建议用极其微小的 epsilon，但在 VRP 整数/浮点分值场景下，直接比较 < 通常符合预期
        if local_fitness < bks_fitness:
            # 本地解优于榜单 -> 保留
            print(f"{instance_name:<25} | {local_fitness:<12} | {bks_fitness:<12} | ** KEEP ** (Better)")
            kept_count += 1
        else:
            # 本地解不如或等于榜单 -> 删除
            try:
                os.remove(file_path)
                print(f"{instance_name:<25} | {local_fitness:<12} | {bks_fitness:<12} | DELETE (Not Best)")
                removed_count += 1
            except OSError as e:
                print(f"删除失败 {file_name}: {e}")

    print("-" * 60)
    print(f"处理完成。保留: {kept_count} 个, 删除: {removed_count} 个。")


# --- 主程序执行 ---
if __name__ == "__main__":
    # 1. 获取在线榜单数据
    leaderboard = get_cvrplib_instances_float()

    # 2. 如果成功获取到了数据，执行过滤
    if leaderboard:
        # 确保这里填写你真实的文件夹名称
        folder_path = "to_sub_sols"

        # 建议先备份一下你的文件夹，以防逻辑误删
        filter_solutions_by_leaderboard(leaderboard, folder_path)
    else:
        print("由于无法获取榜单数据，取消本地过滤操作。")