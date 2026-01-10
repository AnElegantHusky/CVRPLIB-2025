import os
import shutil


def copy_files_by_name(src_path, dst_path, name_list):
    """
    将 src_path 下文件名包含 name_list 中元素的文件复制到 dst_path
    """
    # 1. 检查目标路径是否存在，不存在则创建
    if not os.path.exists(dst_path):
        os.makedirs(dst_path)
        print(f"已创建目标文件夹: {dst_path}")

    # 2. 统计计数器
    copy_count = 0

    # 3. 遍历源文件夹下的所有文件
    # 注意：如果需要遍历子文件夹，请将 os.listdir 换成 os.walk
    for filename in os.listdir(src_path):
        full_file_path = os.path.join(src_path, filename)

        # 确保是文件而不是文件夹
        if os.path.isfile(full_file_path):
            # 4. 核心逻辑：检查文件名是否包含 list 中的任何一个字符串
            # 使用 any() 函数进行高效判断
            if any(name in filename for name in name_list):
                try:
                    shutil.copy2(full_file_path, dst_path)  # copy2 保留文件元数据（如创建时间）
                    print(f"已复制: {filename}")
                    copy_count += 1
                except Exception as e:
                    print(f"复制 {filename} 失败: {e}")

    print(f"--- 处理完成，共复制了 {copy_count} 个文件 ---")


# --- 配置区域 ---
if __name__ == "__main__":
    # 在这里修改你的路径和名称列表
    # source_directory = '../test-1day/Mahdi_baseline'  # 源文件夹路径
    # destination_directory = r"./Mahdi_baseline"  # 目标文件夹路径

    source_directory = './test-bks/AILSII_continue_1'  # 源文件夹路径
    destination_directory = r"./test-continue-XLDemo/AILSII_continue_1"  # 目标文件夹路径
    target_names = [
        'XLTEST-n1048-k139',
        'XLTEST-n2168-k625',
        'XLTEST-n3101-k685',
        'XLTEST-n4245-k164',
        'XLTEST-n5174-k170',
        'XLTEST-n5649-k365',
        'XLTEST-n6034-k1234',
        'XLTEST-n8575-k343'
    ]

    copy_files_by_name(source_directory, destination_directory, target_names)