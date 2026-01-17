import os
import datetime
import stat
from pathlib import Path, PurePosixPath
from fabric import Connection

# ================= 配置区域 (保持不变) =================
servers = [
    {
        "host": "10.90.91.100",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/",
    },
    {
        "host": "10.90.91.101",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.124",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/CVRPLIB-2025-all-in-one/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.125",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.126",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.127",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.163",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.167",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.49",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.51",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.231",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.232",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
]


# ===========================================

# 定义递归下载函数
def download_recursive(sftp, remote_dir, local_base, remote_root_base):
    """
    sftp: sftp连接对象
    remote_dir: 当前正在遍历的远程目录 (PurePosixPath)
    local_base: 本地根目录 (Path)
    remote_root_base: 远程下载的起始根目录 (用于计算相对路径)
    """
    try:
        # 获取当前目录下的所有条目（包含属性，用于判断是文件还是文件夹）
        for item in sftp.listdir_attr(str(remote_dir)):
            remote_path = remote_dir / item.filename

            # 计算相对路径：例如 remote is /.../log_buffer/ins1/a.db, root is /.../log_buffer
            # relative_path 就是 ins1/a.db
            relative_path = remote_path.relative_to(remote_root_base)

            # 拼接本地路径： ./timestamp/ins1/a.db
            local_path = local_base / relative_path

            # 判断是文件夹还是文件
            if stat.S_ISDIR(item.st_mode):
                # 如果是文件夹，在本地创建对应的文件夹，然后递归
                local_path.mkdir(parents=True, exist_ok=True)
                download_recursive(sftp, remote_path, local_base, remote_root_base)
            else:
                # 确保父目录存在
                local_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"   📥 下载: {relative_path}")
                # 下载文件
                sftp.get(str(remote_path), str(local_path))

    except Exception as e:
        print(f"   ⚠️  遍历或下载目录 {remote_dir} 时出错: {e}")


# ================= 主程序 =================

# 1. 准备本地下载目录
current_dir = Path(__file__).resolve().parent # TODO
timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
# 所有服务器的文件都将汇总到这个文件夹
download_root_dir = current_dir / timestamp_str
download_root_dir.mkdir(exist_ok=True)

print(f"📂 本地汇总目录: {download_root_dir}")
print(f"ℹ️  注意: 不同服务器若包含相同的 [instance_name/文件名]，后下载的将覆盖先下载的。")

to_run_servers = [
    "10.90.91.100",
    "10.90.91.101",
    "10.90.91.124",
    "10.90.91.125",
    "10.90.91.126",
    "10.90.91.127",
    "10.90.91.163",
    "10.90.91.167",
    "10.90.91.49",
    "10.90.91.51",
    "10.90.91.231",
    "10.90.91.232",
]

for srv in servers:
    if srv['host'] not in to_run_servers:
        continue

    try:
        print(f"\n🔗 正在连接: {srv['host']}...")

        conn = Connection(
            host=srv['host'],
            user=srv['user'],
            port=srv['port'],
            connect_kwargs={"password": srv['password']},
            connect_timeout=10
        )

        # 构造远程 log_buffer 路径
        remote_base = PurePosixPath(srv['base_path'])
        remote_log_buffer = remote_base / "log_buffer"

        # 开启 SFTP 进行文件操作
        with conn.sftp() as sftp:
            try:
                # 检查远程目录是否存在
                sftp.stat(str(remote_log_buffer))

                # 开始递归下载
                # 参数：sftp对象, 当前远程路径, 本地根路径, 远程基准路径(用于截取相对路径)
                download_recursive(sftp, remote_log_buffer, download_root_dir, remote_log_buffer)

            except FileNotFoundError:
                print(f"   ❌ 远程目录不存在: {remote_log_buffer}")
            except IOError as e:
                print(f"   ❌ SFTP 错误: {e}")

        print(f"✅ {srv['host']}: 处理完成")
        conn.close()

    except Exception as e:
        print(f"❌ {srv.get('host', 'Unknown')}: 连接失败 - {str(e)}")

print(f"\n🏁 所有任务执行完毕。文件已合并保存在: {download_root_dir}")