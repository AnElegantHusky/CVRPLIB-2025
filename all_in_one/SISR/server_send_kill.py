import os
from fabric import Connection

# ================= 配置区域 =================

# 1. 服务器清单 (保持与原文件一致)
servers = [
    {
        "host": "10.90.91.100",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.101",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.124",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.125",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.126",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.127",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.163",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.167",
        "user": "ei",
        "password": "ei@noah2012",
        "port": 22,
    },
    {
        "host": "10.90.91.49",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
    },
    {
        "host": "10.90.91.51",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
    },
    {
        "host": "10.90.91.231",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
    },
    {
        "host": "10.90.91.232",
        "user": "cvrp",
        "password": "123456",
        "port": 22,
    },
]

# 2. 需要执行的目标服务器列表
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

# ===========================================

print(f"🛑 开始批量停止任务...")

for srv in servers:
    host_ip = srv['host']

    if host_ip not in to_run_servers:
        continue

    try:
        print(f"\n🔗 连接: {host_ip} ...")

        conn = Connection(
            host=host_ip,
            user=srv['user'],
            port=srv['port'],
            connect_kwargs={"password": srv['password']},
            connect_timeout=10
        )

        # 定义清理命令
        # warn=True: 如果没有找到进程(pkill返回1)，不要抛出异常，继续执行下一条

        print(f"   🔪 正在清理 python3 进程...")
        conn.run("docker exec cvrplib pkill -f python3", warn=True, hide=True)

        print(f"   🔪 正在清理 run_all.sh 进程...")
        conn.run("docker exec cvrplib pkill -f run_all.sh", warn=True, hide=True)

        print(f"✅ {host_ip}: 清理命令已执行完毕")
        conn.close()

    except Exception as e:
        print(f"❌ {host_ip}: 连接或执行失败 - {str(e)}")

print("\n🏁 所有服务器清理完毕。")