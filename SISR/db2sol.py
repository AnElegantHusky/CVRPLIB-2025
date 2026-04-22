import sqlite3
import os
import json
from pathlib import Path
from datetime import datetime
import traceback
import ast


def sqlite_best_to_sol(db_file_path, output_sol_path):
    """
    读取 global_best 表中的最佳解，并导出为 .sol 文件
    :param db_file_path: SQLite数据库文件路径
    :param output_sol_path: 输出的 .sol 文件路径
    """
    if not os.path.exists(db_file_path):
        print(f"错误：数据库文件 {db_file_path} 不存在！")
        return

    conn = None
    try:
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()

        # 查询 global_best 表中的 solution 和 score
        # 因为 id check(id=1)，所以直接查 id=1 即可
        sql = "SELECT solution, score FROM global_best WHERE id = 1;"
        cursor.execute(sql)
        row = cursor.fetchone()

        if not row:
            print("错误：global_best 表中没有数据。")
            return

        solution_text, score = row

        # 处理初始插入的空数据情况 (INSERT OR IGNORE ... VALUES (..., ''))
        if not solution_text:
            print("警告：数据库中的 solution 字段为空，无法导出路径。")
            return

        # ==========================================
        # 数据解析 (假设 solution 是 JSON 格式的列表)
        # ==========================================
        try:
            # 尝试将 TEXT 解析为 Python list，例如: [[1, 2], [3, 4]]
            # routes = json.loads(solution_text)
            routes = ast.literal_eval(solution_text)
        except Exception as e:
            traceback.print_exc()
            print("错误：solution 字段不是有效的 JSON 格式，无法解析。")
            print(f"原始内容: {solution_text[:50]}...")
            return

        # ==========================================
        # 写入 .sol 文件
        # ==========================================
        with open(output_sol_path, 'w', newline='', encoding='utf-8') as f:
            # 1. 遍历并写入路径
            # 输出格式: Route #1: node1 node2 ...
            for index, route in enumerate(routes):
                # 将节点列表转换为空格分隔的字符串
                # 假设 route 是 [1, 2, 3] -> "1 2 3"
                route_str = " ".join(map(str, route))
                f.write(f"Route #{index + 1}: {route_str}\n")

            # 2. 写入总分 (Cost)
            # 输出格式: Cost 12345.000000
            f.write(f"Cost {score:.6f}\n")

        print(f"成功导出最佳方案到 {output_sol_path}")
        print(f"包含路径数: {len(routes)}")
        print(f"总成本 (Cost): {score}")

    except sqlite3.Error as e:
        print(f"SQLite操作错误：{e}")
    except Exception as e:
        print(f"导出过程中发生错误：{e}")
        traceback.format_exc()
    finally:
        if conn:
            conn.close()


# 主程序入口
if __name__ == "__main__":
    SISR_PATH = Path(__file__).resolve().parent

    DB_ROOT_PATH = SISR_PATH / 'log_buffer'
    OUTPUT_ROOT_PATH = SISR_PATH / 'output_sol'

    now = datetime.now()
    crt_time = now.strftime("%Y-%m-%d_%H-%M-%S")
    OUTPUT_PATH = OUTPUT_ROOT_PATH / crt_time
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)

    for DB_PATH in DB_ROOT_PATH.rglob('*.db'):
        instance_name = DB_PATH.parent.name
        sol_path = OUTPUT_PATH / f'{instance_name}.sol'
        sqlite_best_to_sol(DB_PATH, sol_path)
