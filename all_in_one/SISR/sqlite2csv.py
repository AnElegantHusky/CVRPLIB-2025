import sqlite3
import csv
import os
import datetime
import shutil


def sqlite_to_csv(db_file_path, output_dir):
    """
    将SQLite数据库中的所有表导出为CSV文件，并保存到指定目录
    """
    # 检查数据库文件是否存在
    if not os.path.exists(db_file_path):
        print(f"警告：数据库文件 {db_file_path} 不存在，跳过。")
        return

    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    conn = None
    try:
        conn = sqlite3.connect(db_file_path)
        cursor = conn.cursor()

        # 获取数据库中所有表的名称
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        if not tables:
            print(f"[{db_file_path}] 数据库为空（无表）")
            return

        # 遍历每个表并导出
        for table_name in tables:
            table_name = table_name[0]
            csv_file_name = os.path.join(output_dir, f"{table_name}.csv")

            cursor.execute(f"SELECT * FROM {table_name};")
            rows = cursor.fetchall()

            if cursor.description:
                column_names = [description[0] for description in cursor.description]
            else:
                column_names = []

            with open(csv_file_name, 'w', newline='', encoding='utf-8') as csv_file:
                csv_writer = csv.writer(csv_file)
                if column_names:
                    csv_writer.writerow(column_names)
                csv_writer.writerows(rows)

            print(f"  -> 已导出: {table_name}.csv")

    except sqlite3.Error as e:
        print(f"SQLite 错误 [{db_file_path}]: {e}")
    except Exception as e:
        print(f"导出错误 [{db_file_path}]: {e}")
    finally:
        if conn:
            conn.close()


def compress_folder(source_dir, output_filename):
    """
    将文件夹压缩为zip文件
    :param source_dir: 要压缩的文件夹路径
    :param output_filename: 输出文件名（不带后缀）
    """
    print(f"\n正在打包文件到 {output_filename}.zip ...")
    try:
        # make_archive 会自动添加 .zip 后缀
        shutil.make_archive(output_filename, 'zip', source_dir)
        print(f"打包完成：{output_filename}.zip")
    except Exception as e:
        print(f"打包失败: {e}")


if __name__ == "__main__":
    # 1. 配置输入目录
    SOURCE_ROOT = "./log_buffer"

    # 2. 生成带时间戳的输出目录名 (格式: log_csv_YYYYMMDDHHMM)
    current_time = datetime.datetime.now().strftime("%Y%m%d%H%M")
    OUTPUT_ROOT_NAME = f"log_csv_{current_time}"
    OUTPUT_ROOT_PATH = os.path.join(".", OUTPUT_ROOT_NAME)

    # 检查源目录
    if not os.path.exists(SOURCE_ROOT):
        print(f"错误：源目录 {SOURCE_ROOT} 不存在！")
        exit(1)

    print(f"输出目录将设置为: {OUTPUT_ROOT_PATH}")
    print(f"开始扫描 {SOURCE_ROOT} ...")

    has_processed_data = False

    # 3. 遍历并转换
    for folder_name in os.listdir(SOURCE_ROOT):
        folder_path = os.path.join(SOURCE_ROOT, folder_name)

        if os.path.isdir(folder_path):
            db_path = os.path.join(folder_path, "shared.db")

            if os.path.exists(db_path):
                # 构建输出路径: log_csv_2023.../文件夹名/
                target_output_dir = os.path.join(OUTPUT_ROOT_PATH, folder_name)

                print(f"\n处理目录: {folder_name}")
                sqlite_to_csv(db_path, target_output_dir)
                has_processed_data = True

    # 4. 打包压缩
    if has_processed_data and os.path.exists(OUTPUT_ROOT_PATH):
        compress_folder(OUTPUT_ROOT_PATH, OUTPUT_ROOT_NAME)
        print("\n所有操作成功完成。")
    else:
        print("\n未找到可处理的 shared.db 文件，未生成输出。")