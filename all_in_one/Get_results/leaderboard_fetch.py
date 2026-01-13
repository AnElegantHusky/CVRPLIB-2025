import requests
from bs4 import BeautifulSoup


def get_cvrplib_instances_float():
    """
    爬取 CVRPLIB 数据并将第三列的金额/数值转换为浮点数。

    针对格式: "$380{,}211.00" -> 380211.0
    处理逻辑: 去除 '$', ',', '{', '}' 字符，然后转 float。
    """
    target_url = "https://galgos.inf.puc-rio.br/cvrplib/index.php/en/bks_challenge/score/instances"

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    try:
        response = requests.get(target_url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # 定位表格
        table = soup.select_one('main section table')
        if not table:
            table = soup.find('table')

        if not table:
            return {}

        data_dict = {}
        tbody = table.find('tbody')

        if tbody:
            rows = tbody.find_all('tr')
            for row in rows:
                cols = row.find_all('td')

                if len(cols) >= 3:
                    key = cols[0].get_text(strip=True)
                    raw_value = cols[2].get_text(strip=True)

                    # --- 数据清洗核心逻辑 ---
                    try:
                        # 1. 去除干扰字符：$, ,, {, }
                        # 使用 replace 链式调用清洗字符串
                        clean_value = raw_value.replace('$', '').replace(',', '').replace('{', '').replace('}', '')

                        # 2. 转换为浮点数
                        float_value = float(clean_value)

                        # 3. 存入字典
                        data_dict[key] = float_value

                    except ValueError:
                        # 如果转换失败（例如遇到空值或文字），可以选择跳过或保留原字符串
                        print(f"警告: 无法转换数值 '{raw_value}' (Key: {key})")
                        continue  # 跳过该行

        return data_dict

    except Exception as e:
        print(f"发生错误: {e}")
        return {}


# --- 测试与验证 ---
if __name__ == "__main__":
    # 模拟测试一下清洗逻辑
    test_str = "$380{,}211.00"
    cleaned = float(test_str.replace('$', '').replace(',', '').replace('{', '').replace('}', ''))
    print(f"逻辑验证: '{test_str}' -> {cleaned} (类型: {type(cleaned)})")
    print("-" * 30)

    # 运行爬虫
    result = get_cvrplib_instances_float()

    print(f"成功爬取 {len(result)} 条数据。")
    if len(result) > 0:
        first_key = list(result.keys())[0]
        print(f"示例数据: Key='{first_key}', Value={result[first_key]}, Type={type(result[first_key])}")

    for k, v in result.items():
        print(f"{k}: {v}")