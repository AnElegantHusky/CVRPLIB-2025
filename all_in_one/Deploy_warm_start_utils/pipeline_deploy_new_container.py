import time
from rich.table import Table
from config import servers as SERVER_MANIFEST
from server_utils import ServerNode, console

# ================= 配置 =================
DOCKER_IMAGE = "cvrplib_sy5"
NEW_CONTAINER_NAME = "warm_start"

# 容器内挂载点固定为 /app
# 挂载后结构: /app/all_in_one/SISR/...
CONTAINER_ROOT_DIR = "/app"

# [开关] 定义要运行的服务器 IP 列表
to_run_servers = [
    # "10.90.91.100", # 已测试通过
    # "10.90.91.101",
    "10.90.91.124",  # 本次重点测试对象
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


def main():
    console.rule("[bold blue]启动 Warm Start 部署 (指定列表)[/bold blue]")

    # 1. 筛选并连接服务器
    nodes = []
    for conf in SERVER_MANIFEST:
        if conf['host'] in to_run_servers:
            node = ServerNode(conf)
            if node.connect():
                nodes.append(node)

    if not nodes:
        console.print("[yellow]⚠️  没有选中任何服务器，请检查 to_run_servers 列表[/yellow]")
        return

    # 2. 执行任务
    for node in nodes:
        console.print(f"\n[bold green]>>> 节点: {node.host}[/bold green]")

        # --- Step 1: 同步文件 ---
        if not node.sync_artifacts():
            continue

        # --- Step 2: 清理旧容器 ---
        node.run_cmd(f"docker rm -f {NEW_CONTAINER_NAME}")

        # --- Step 3: 启动容器 ---
        # 挂载宿主机的 Top 目录 (Warm_Start_Deploy_Hybrid) 到容器 /app
        mount_arg = f"-v {node.path_B_top}:{CONTAINER_ROOT_DIR}"

        docker_cmd = (
            f"docker run --init -it -d "
            f"--name {NEW_CONTAINER_NAME} "
            f"-w {CONTAINER_ROOT_DIR} "
            f"{mount_arg} "
            f"{DOCKER_IMAGE} "
            f"/bin/bash"
        )

        console.print(f"🚀 创建容器: {NEW_CONTAINER_NAME}")
        ok, res = node.run_cmd(docker_cmd)

        if not ok:
            console.print(f"   ❌ 启动失败: {res}")
            continue

        console.print(f"   ✅ 容器已启动 (ID: {res[:12]})")

        # --- Step 4: 自动配置 Python 环境 ---
        console.print("   📦 正在安装依赖 (pip install)...")

        # 路径: all_in_one/SISR/requirements2.txt (相对于 /app)
        req_path = "all_in_one/SISR/requirements2.txt"
        req_cmd = f"pip install -r {req_path}"

        ok_pip, res_pip = node.run_cmd(f"docker exec {NEW_CONTAINER_NAME} {req_cmd}")

        if ok_pip:
            console.print("   ✅ 环境配置完成")
        else:
            console.print(f"   ⚠️  环境配置可能出错: {res_pip}")

    print_status(nodes)


def print_status(nodes):
    table = Table(title=f"容器状态: {NEW_CONTAINER_NAME}")
    table.add_column("IP", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Mount Path", style="magenta")

    for node in nodes:
        ok, out = node.run_cmd(f"docker ps -f name={NEW_CONTAINER_NAME} --format '{{{{.Status}}}}'")
        status = out if ok and out else "Not Found"
        color = "green" if "Up" in status else "red"
        # 打印出实际挂载的 Top 路径，方便检查是否是预期的 CVRPLIB... 路径
        table.add_row(node.host, f"[{color}]{status}[/{color}]", node.path_B_top)

    console.print(table)


if __name__ == "__main__":
    main()