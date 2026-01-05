import os
import pandas as pd


def clean_csv_columns_semicolon(root_path):
    """
    遍历 root_path 下所有文件夹，找到以分号(;)分隔的 csv 文件。
    如果文件有 3 列，则去除最后一列并覆盖保存。
    """
    processed_count = 0

    for dirpath, dirnames, filenames in os.walk(root_path):
        for filename in filenames:
            if filename.lower().endswith(".csv"):
                file_path = os.path.join(dirpath, filename)

                try:
                    # [关键修改 1] 指定 sep=';' 以正确识别分号分隔符
                    df = pd.read_csv(file_path, sep=';')

                    # 检查列数
                    current_cols = df.shape[1]

                    if current_cols == 3:
                        print(f"检测到3列，正在修正: {filename}")

                        # 保留前两列
                        df_new = df.iloc[:, :2]

                        # [关键修改 2] 保存时也必须指定 sep=';'，否则会变成逗号
                        df_new.to_csv(file_path, index=False, sep=';')

                        processed_count += 1
                    elif current_cols == 1:
                        print(f"警告: {filename} 被识别为 1 列。请确认文件确实是用分号分隔的吗？")
                    else:
                        # 既不是3列也不是1列，忽略
                        pass

                except Exception as e:
                    print(f"处理文件 {filename} 时出错: {e}")

    print(f"--- 全部完成，共修改了 {processed_count} 个 CSV 文件 ---")

# --- 配置区域 ---
if __name__ == "__main__":
    # 在这里修改你要遍历的根目录
    # target_directory = r"./AILS2_Eta_Cycle_1800_0.1"
    target_directory = '../test-eta'

    # 检查是否安装了 pandas
    try:
        import pandas

        clean_csv_columns_semicolon(target_directory)
    except ImportError:
        print("错误：请先安装 pandas 库。在终端运行: pip install pandas")