import os
from fabric import Connection

# ================= 配置区域 =================
# 服务器清单（保持你原来的配置不变）
servers = [
    {"host": "10.90.91.100", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.101", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.124", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/CVRPLIB-2025-all-in-one/all_in_one/SISR/"},
    {"host": "10.90.91.125", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.126", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.127", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.163", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.167", "user": "ei", "password": "ei@noah2012", "port": 22,
     "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.49", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.51", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.231", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
    {"host": "10.90.91.232", "user": "cvrp", "password": "123456", "port": 22,
     "base_path": "/home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"},
]

# 指定需要执行的服务器
to_run_servers = [s['host'] for s in servers]  # 默认抓取全部

# 本地保存的基准目录 (即当前脚本所在的 SISR 目录)
local_base_dir = os.path.dirname(os.path.abspath(__file__))

# ===========================================

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

        # 1. 确定远程 log_buffer 的绝对路径
        remote_log_root = os.path.join(srv['base_path'], "log_buffer").replace('\\', '/')

        # 2. 在远程搜索所有的 shared.db 文件
        # 使用 find 命令找出类似 SISR/log_buffer/instance_name/shared.db 的所有文件
        print(f"🔎 正在检索远程数据库文件: {remote_log_root} ...")
        find_cmd = f"find {remote_log_root} -name 'shared.db'"
        result = conn.run(find_cmd, hide=True, warn=True)

        if not result.ok or not result.stdout.strip():
            print(f"⚠️  在 {srv['host']} 上未找到任何 shared.db")
            conn.close()
            continue

        remote_files = result.stdout.strip().split('\n')

        # 3. 循环下载
        for remote_file in remote_files:
            # 提取 instance_name/shared.db 部分
            # 假设 remote_file 是 /home/.../SISR/log_buffer/inst_1/shared.db
            # 我们需要把 log_buffer/inst_1/shared.db 这部分拼接到本地
            rel_path = os.path.relpath(remote_file, srv['base_path'])  # 获取相对 SISR 的路径
            local_full_path = os.path.join(local_base_dir, rel_path)

            # 确保本地目录存在
            local_dir = os.path.dirname(local_full_path)
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)

            print(f"   📥 下载: {srv['host']}:{rel_path} -> {local_full_path}")

            # 执行下载
            conn.get(remote_file, local=local_full_path)

        print(f"✅ {srv['host']}: 抓取完成 (共 {len(remote_files)} 个文件)")
        conn.close()

    except Exception as e:
        print(f"❌ {srv.get('host', 'Unknown')}: 失败 - {str(e)}")

print("\n🏁 所有服务器数据抓取完毕。")