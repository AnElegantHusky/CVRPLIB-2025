import os
from fabric import Connection

# ================= 配置区域 =================

# 1. 定义任务分配 (根据图片内容整理)
# Key: 服务器IP, Value: (Start, End)
task_ranges = {
    "10.90.91.100": (0, 3),
    "10.90.91.101": (3, 9),
    "10.90.91.124": (9, 15),
    "10.90.91.125": (15, 21),
    "10.90.91.126": (21, 27),
    "10.90.91.127": (27, 32),
    "10.90.91.163": (32, 37),
    "10.90.91.167": (37, 42),
    "10.90.91.49": (42, 49),
    "10.90.91.51": (49, 56),
    "10.90.91.231": (56, 78),
    "10.90.91.232": (78, 100),
}

# 2. 服务器清单 (保持原有配置)
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
        "base_path": "/home/ei/workspace/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/"
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

print(f"🚀 开始批量执行命令...")

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
    host_ip = srv['host']

    # 检查该 IP 是否在我们的任务列表里
    if host_ip not in task_ranges:
        print(f"⚠️ 跳过 {host_ip}: 未在任务列表中定义参数")
        continue

    # 获取参数
    start_arg, end_arg = task_ranges[host_ip]

    try:
        print(f"\n🔗 连接: {host_ip} (范围: {start_arg}-{end_arg})...")

        conn = Connection(
            host=host_ip,
            user=srv['user'],
            port=srv['port'],
            connect_kwargs={"password": srv['password']},
            connect_timeout=10
        )

        # 构造命令
        # 1. 切换到 base_path
        # 2. 执行 nohup (后台运行)，将日志输出到 run_X_Y.log，防止脚本阻塞
        remote_path = srv['base_path'].rstrip('/')
        # log_file = f"run_{start_arg}_{end_arg}.log"

        # 这里的命令逻辑是：
        # cd 到目录 && nohup bash main.sh 参数 > 日志 2>&1 &
        # & 在最后表示后台运行
        cmd = (
            f"cd {remote_path} && "
            f"bash main.sh {start_arg} {end_arg}"
        )

        print(f"   💻 发送命令: {cmd}")

        # 执行命令
        # 注意: 因为用了 nohup ... &，命令会瞬间返回，Python 脚本会立即继续
        conn.run(cmd, hide=True)

        print(f"✅ {host_ip}: 命令已发送 (后台运行中)")
        conn.close()

    except Exception as e:
        print(f"❌ {host_ip}: 执行失败 - {str(e)}")

print("\n🏁 所有命令发送完毕。")