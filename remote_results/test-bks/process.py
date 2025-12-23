import os
import shutil


def move_files(source_dir, target_dir):
    """
    将 source_dir 中以 _1.csv 和 _1.sol 结尾的文件剪切到 target_dir。
    """
    # 1. 检查源路径是否存在
    if not os.path.exists(source_dir):
        print(f"❌ 错误：源路径不存在 -> {source_dir}")
        return

    # 2. 检查目标路径是否存在，不存在则创建
    if not os.path.exists(target_dir):
        try:
            os.makedirs(target_dir)
            print(f"📁 已创建目标文件夹 -> {target_dir}")
        except OSError as e:
            print(f"❌ 无法创建目标文件夹: {e}")
            return

    # 定义需要匹配的后缀
    valid_extensions = ('_2.csv', '_2.sol')

    moved_count = 0

    print(f"🚀 开始扫描目录: {source_dir} ...")

    # 3. 遍历源目录下的所有文件
    for filename in os.listdir(source_dir):
        # 检查文件名是否以指定后缀结尾
        if filename.endswith(valid_extensions):
            source_file = os.path.join(source_dir, filename)
            target_file = os.path.join(target_dir, filename)

            try:
                # 执行剪切（移动）操作
                shutil.move(source_file, target_file)
                print(f"✅ 已移动: {filename}")
                moved_count += 1
            except Exception as e:
                print(f"⚠️ 移动失败 {filename}: {e}")

    print("-" * 30)
    print(f"🎉 操作完成！共移动了 {moved_count} 个文件。")


if __name__ == "__main__":
    # --- 请在这里修改你的路径 ---
    # Windows 路径示例: r"C:\Users\Name\Documents\Source"
    # Mac/Linux 路径示例: "/Users/name/data/source"

    source_path = r"AILSII_continue_eoh_1"  # 输入存放文件的文件夹
    target_path = r"AILSII_continue_eoh_2"  # 输入想移动到的文件夹

    move_files(source_path, target_path)