import time
from pathlib import Path
from rich.table import Table
from rich.console import Console
from fabric import Connection
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================
DOCKER_IMAGE = "cvrplib_sy5"
NEW_CONTAINER_NAME = "warm_start"

# 定义要操作的服务器 IP (请根据需要取消注释)
to_run_servers = [
    "10.90.91.100",
    # "10.90.91.101",
    # "10.90.91.124",
    # "10.90.91.125",
    # "10.90.91.126",
    # "10.90.91.127",
    # "10.90.91.163",
    # "10.90.91.167",
    # "10.90.91.49",
    # "10.90.91.51",
    # "10.90.91.231",
    # "10.90.91.232",
]


def deploy_containers():
    # 筛选出要部署的节点
    target_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    console.print(f"📋 目标服务器数量: {len(target_nodes)}")

    for s in target_nodes:
        host = s['host']
        user = s['user']
        password = s['password']
        port = s['port']

        # 获取原始配置路径 (指向 .../SISR/)
        ws_path_raw = s.get('warm_start_work_path')
        main_path_raw = s.get('main_work_path')

        if not ws_path_raw or not main_path_raw:
            console.print(f"[bold red]❌ 跳过 {host}: 缺少 path 配置[/bold red]")
            continue

        # --- 1. 计算挂载路径 (爷节点) ---
        # 原始: .../Warm_Start_Deploy_Hybrid/all_in_one/SISR/
        # 爷节点: .../Warm_Start_Deploy_Hybrid/
        ws_path_obj = Path(ws_path_raw.rstrip('/'))  # 去掉末尾斜杠以确保 parent 计算正确
        host_mount_path = ws_path_obj.parent.parent  # 往上跳两级

        console.print(f"\n[bold cyan]Process Node: {host}[/bold cyan]")
        console.print(f"   📂 原始路径: {ws_path_raw}")
        console.print(f"   📂 挂载路径 (爷节点): {host_mount_path}")

        try:
            # 建立 SSH 连接
            conn = Connection(host=host, user=user, port=port, connect_kwargs={"password": password})

            # --- 2. 清理旧容器 ---
            console.print(f"   🗑️  清理旧容器 ({NEW_CONTAINER_NAME})...")
            # -f 强制删除运行中的容器
            conn.run(f"docker rm -f {NEW_CONTAINER_NAME}", warn=True, hide=True)

            # --- 3. 启动新容器 ---
            # 逻辑说明：
            # 1. -v {host_mount_path}:/app  -> 将整个 Warm_Start_Deploy_Hybrid 挂载到 /app
            # 2. -w /app/all_in_one/SISR    -> 将工作目录设回代码所在深层目录，这样 pip 和 python 命令不需要改路径
            # 3. -v {main_path_raw}:/cvrplib_link -> 保持数据交互挂载不变

            # 容器内的代码目录
            container_work_dir = "/app/all_in_one/SISR"

            docker_cmd = (
                f"docker run --init -it -d "
                f"--name {NEW_CONTAINER_NAME} "
                f"-w {container_work_dir} "  # 设置工作目录为代码目录
                f"-v {host_mount_path}:/app "  # 挂载爷节点到 /app
                f"-v {main_path_raw}:/cvrplib_link "  # 保持与主进程的交互通道
                f"{DOCKER_IMAGE} "
                f"/bin/bash"
            )

            console.print(f"   🚀 正在启动容器...")
            res = conn.run(docker_cmd, warn=True, hide=True)

            if res.failed:
                console.print(f"   ❌ 启动失败: {res.stderr.strip()}")
                continue

            console.print(f"   ✅ 容器已启动 (ID: {res.stdout.strip()[:12]})")

            # --- 4. 配置 Python 环境 ---
            # 因为我们设定了 -w /app/all_in_one/SISR，所以这里直接 pip install requirements2.txt 即可
            console.print("   📦 安装依赖 (pip install)...")
            pip_res = conn.run(f"docker exec {NEW_CONTAINER_NAME} pip install -r requirements2.txt", warn=True,
                               hide=True)

            if pip_res.ok:
                console.print("   ✅ 环境依赖安装完成")
            else:
                console.print(f"   ⚠️  依赖安装警告: {pip_res.stderr.strip()}")

        except Exception as e:
            console.print(f"[bold red]💥 连接或执行异常 {host}: {e}[/bold red]")
            continue

    console.print("\n[bold green]🎉 所有节点部署流程结束[/bold green]")


if __name__ == "__main__":
    deploy_containers()