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

print(f"🛑 开始执行【深度清理】任务...")

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

        # === 定义清理命令序列 (执行顺序很重要) ===
        kill_cmds = [
            # 1. 【关键】先杀 Shell 脚本
            # 防止杀掉 Python 后，脚本里的循环又立刻启动新的 Python
            "docker exec cvrplib pkill -f run_all.sh",

            # 2. 【核心】强杀主 Python 程序
            # 使用 -9 强制杀死，防止进程卡死无法响应
            "docker exec cvrplib pkill -9 -f main_for_all_final.py",

            # 3. 【关联】通过路径关键字杀子进程
            # 凡是命令行参数里包含 'all_in_one' 的进程全部干掉
            "docker exec cvrplib pkill -9 -f all_in_one",

            # 4. 【兜底】杀掉容器内所有 python3 进程 (最彻底)
            # 如果前面的步骤有漏网之鱼（比如子进程改了名），这一步能保证干净
            "docker exec cvrplib pkill -9 -f python3",

            # -f java 会匹配 'java -jar ...' 等所有 java 相关命令
            "docker exec cvrplib pkill -9 -f java",
        ]

        print(f"   🔪 正在执行深度清理...")

        for cmd in kill_cmds:
            # warn=True: 即使没找到进程报错，也不中断脚本，继续执行下一条
            conn.run(cmd, warn=True, hide=True)

        print(f"✅ {host_ip}: 清理完毕")
        conn.close()

    except Exception as e:
        print(f"❌ {host_ip}: 连接或执行失败 - {str(e)}")

print("\n🏁 所有服务器清理完毕。")