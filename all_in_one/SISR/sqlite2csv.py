import sqlite3
import csv
import os

def sqlite_to_csv(db_file_path):
    """
    将SQLite数据库中的所有表导出为CSV文件
    :param db_file_path: SQLite数据库文件路径
    """
    # 检查数据库文件是否存在
    if not os.path.exists(db_file_path):
        print(f"错误：数据库文件 {db_file_path} 不存在！")
        return

    try:
        # 连接SQLite数据库
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()

        # 获取数据库中所有表的名称
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print("数据库中没有找到任何表！")
            conn.close()
            return

        # 遍历每个表并导出为CSV
        for table_name in tables:
            table_name = table_name[0]  # 提取表名（元组转字符串）
            csv_file_name = f"{table_name}.csv"

            # 查询表中所有数据
            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()

            # 获取表的列名
            column_names = [description[0] for description in cursor.description]

            # 写入CSV文件
            with open(csv_file_name, 'w', newline='', encoding='utf-8') as csv_file:
                csv_writer = csv.writer(csv_file)
                # 写入列名（表头）
                csv_writer.writerow(column_names)
                # 写入数据行
                csv_writer.writerows(rows)

            print(f"成功导出表 {table_name} 到 {csv_file_name}")

    except sqlite3.Error as e:
        print(f"SQLite操作错误：{e}")
    except Exception as e:
        print(f"导出过程中发生错误：{e}")
    finally:
        # 确保数据库连接关闭
        if 'conn' in locals() and conn:
            conn.close()

# 主程序入口
if __name__ == "__main__":
    # 请替换为你的SQLite数据库文件路径（相对路径或绝对路径）
    DATABASE_FILE = "your_database.db"  # 示例：test.db
    sqlite_to_csv(DATABASE_FILE)