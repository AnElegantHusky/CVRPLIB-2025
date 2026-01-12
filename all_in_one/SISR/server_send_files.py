import os
from fabric import Connection

# ================= 配置区域 =================
# 服务器清单：每个字典代表一台服务器的独特配置
servers = [
    {
        "host": "10.90.91.100",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/",
    },
    {
        "host": "10.90.91.101",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.124",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.125",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.126",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.127",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.163",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.167",
        "user": "ei",
        "password": "ei@noah2012",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.49",
        "user": "cvrp",
        "password": "123456",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.51",
        "user": "cvrp",
        "password": "123456",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.231",
        "user": "cvrp",
        "password": "123456",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
    {
        "host": "10.90.91.232",
        "user": "cvrp",
        "password": "123456",  # 如果用 SSH Key，这项可以留空或删除
        "port": 22,
        "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
    },
]
# ===========================================
# 本地要分发的文件
file_name_list = [
    'main.sh',
    'main_for_all_final.py',
    'sqlite2csv.py',
    'db2sol.py',
    # 'instances.zip'
]

# 获取当前脚本所在的目录 (兼容 Windows/Linux)
local_base_dir = os.path.dirname(os.path.abspath(__file__))

print(f"📂 本地源目录: {local_base_dir}")

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
    if srv not in to_run_servers:
        continue
    try:
        print(f"\n🔗 正在连接: {srv['host']} (User: {srv['user']})...")

        # 1. 建立连接
        conn = Connection(
            host=srv['host'],
            user=srv['user'],
            port=srv['port'],
            connect_kwargs={"password": srv['password']},
            # 建议加一个超时设置，防止某台机器挂了导致脚本卡死太久
            connect_timeout=10
        )

        for file_name in file_name_list:
            # --- 路径处理优化 ---

            # 1. 本地路径：使用 os.path.join 自动处理 Windows 的反斜杠
            local_full_path = os.path.join(local_base_dir, file_name)

            # 2. 远程路径：Linux 强制使用正斜杠 /
            # 使用 posixpath (或者简单的字符串拼接) 确保是 Linux 风格
            remote_base = srv['base_path'].rstrip('/')
            remote_full_path = f"{remote_base}/{file_name}"

            print(f"   📤 上传: {local_full_path} -> {remote_full_path}")

            # 3. 上传文件
            conn.put(local_full_path, remote=remote_full_path)

            # --- 关键修改：增加执行权限 ---
            if file_name.endswith('.sh'):
                print(f"   🔧 设置权限: chmod +x")
                # hide=True 让它不打印具体命令输出，除非报错
                conn.run(f"chmod +x {remote_full_path}", hide=True)

        print(f"✅ {srv['host']}: 处理完成")
        conn.close()

    except Exception as e:
        print(f"❌ {srv.get('host', 'Unknown')}: 失败 - {str(e)}")

print("\n🏁 所有任务执行完毕。")