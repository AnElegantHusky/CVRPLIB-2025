import time
from pathlib import Path
from rich.console import Console
from fabric import Connection
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================
DOCKER_IMAGE = "cvrplib_sy5"
NEW_CONTAINER_NAME = "warm_start"

to_run_servers = [
    # "10.90.91.100",
    # "10.90.91.101",
    # "10.90.91.124",
    # "10.90.91.125",
    # "10.90.91.126",
    # "10.90.91.127",
    # "10.90.91.163",
    # "10.90.91.167",
    # "10.90.91.49",
    "10.90.91.51",
    # "10.90.91.231",
    # "10.90.91.232",
]


def deploy_containers():
    target_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]
    console.print(f"📋 目标服务器数量: {len(target_nodes)}")

    for s in target_nodes:
        host = s['host']
        user = s['user']
        password = s['password']
        port = s['port']

        # 获取原始字符串
        ws_path_raw = s.get('warm_start_work_path', '')
        main_path_raw = s.get('main_work_path', '')

        if not ws_path_raw or not main_path_raw:
            console.print(f"[yellow]Skipping {host}: Missing config paths[/yellow]")
            continue

        # --- 1. 路径计算与标准化 (关键修复) ---
        # 使用 pathlib 处理，并强制转换为 POSIX 风格 (即使用 / 分割)

        # 处理 Warm Start 路径
        # 假设 raw 是 .../Warm_Start_Deploy_Hybrid/all_in_one/SISR/
        p_ws = Path(ws_path_raw.strip().rstrip('\\').rstrip('/'))
        host_ws_root_obj = p_ws.parent.parent  # 回退两层到 Warm_Start_Deploy_Hybrid

        # 处理 Main 路径
        p_main = Path(main_path_raw.strip().rstrip('\\').rstrip('/'))
        host_main_root_obj = p_main.parent.parent  # 回退两层到 Competition_Deploy_Hybird

        # 【核心步骤】转换为 Linux 字符串
        host_ws_root = host_ws_root_obj.as_posix()
        host_main_root = host_main_root_obj.as_posix()

        # 原始挂载点也要转，防止 config.py 里写了反斜杠
        main_path_linux = p_main.as_posix()

        console.print(f"\n[bold cyan]Process Node: {host}[/bold cyan]")
        console.print(f"   📂 源 (Main): {host_main_root}")
        console.print(f"   📂 靶 (Warm): {host_ws_root}")

        try:
            conn = Connection(host=host, user=user, port=port, connect_kwargs={"password": password})

            # --- 2. 同步文件 (Rsync) ---
            console.print(f"   🔄 同步代码...")
            conn.run(f"mkdir -p {host_ws_root}", hide=True)

            # Rsync 也要用 Linux 路径
            # 注意末尾加斜杠 / 表示同步内容
            rsync_cmd = (
                f"rsync -az "
                f"--exclude 'all_in_one/SISR/log_buffer' "
                f"--exclude '__pycache__' "
                f"--exclude '*.git' "
                f"{host_main_root}/ {host_ws_root}/"
            )

            # 打印命令看看是否正常
            # console.print(f"   [dim]Cmd: {rsync_cmd}[/dim]")

            res_sync = conn.run(rsync_cmd, warn=True, hide=True)
            if res_sync.failed:
                console.print(f"   ❌ 同步失败: {res_sync.stderr}")
                continue

            console.print("   ✅ 代码同步完成")

            # --- 3. 启动容器 ---
            conn.run(f"docker rm -f {NEW_CONTAINER_NAME}", warn=True, hide=True)

            container_work_dir = "/app/all_in_one/SISR"

            # 这里的路径变量现在全都是 / 分割的了，Linux 肯定能认
            docker_cmd = (
                f"docker run --init -it -d "
                f"--name {NEW_CONTAINER_NAME} "
                f"-w {container_work_dir} "
                f"-v {host_ws_root}:/app "
                f"-v {main_path_linux}:/cvrplib_link "
                f"{DOCKER_IMAGE} "
                f"/bin/bash"
            )

            console.print(f"   🚀 启动容器...")
            res = conn.run(docker_cmd, warn=True, hide=True)

            if res.ok:
                console.print(f"   ✅ 启动成功 (ID: {res.stdout.strip()[:12]})")

                # --- 验证环节 ---
                console.print("   🔍 验证容器文件...")
                chk = conn.run(f"docker exec {NEW_CONTAINER_NAME} ls -F /app", warn=True, hide=True)
                if chk.ok and "all_in_one" in chk.stdout:
                    console.print("   🎉 [bold green]验证通过：容器内看到了文件！[/bold green]")
                else:
                    console.print(
                        f"   ⚠️  [bold yellow]警告：容器内似乎还是空的？输出：{chk.stdout.strip()}[/bold yellow]")
            else:
                console.print(f"   ❌ 启动失败: {res.stderr.strip()}")

            # --- 4. 配置环境 ---
            if res.ok:
                console.print("   📦 安装依赖...")
                conn.run(f"docker exec {NEW_CONTAINER_NAME} pip install -r requirements2.txt", warn=True, hide=True)
                console.print("   ✅ 依赖安装完成")

        except Exception as e:
            console.print(f"[bold red]💥 异常: {e}[/bold red]")
            continue

    console.print("\n[bold green]🎉 部署流程结束[/bold green]")


if __name__ == "__main__":
    deploy_containers()