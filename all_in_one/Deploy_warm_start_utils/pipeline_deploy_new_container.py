import time
from rich.table import Table
from config import servers
from server_utils import ServerNode, console

# ================= 配置 =================
DOCKER_IMAGE = "cvrplib_sy5"
NEW_CONTAINER_NAME = "warm_start"
CONTAINER_WORK_DIR = "/app"  # 容器内固定为 /app (对应宿主机的 all_in_one)

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

def main():
    console.rule("[bold blue]启动 Warm Start 基础环境 (无自动运行)[/bold blue]")

    nodes = []
    for conf in to_run_servers:
        node = ServerNode(conf)
        if node.connect():
            nodes.append(node)

    for node in nodes:
        console.print(f"\n[bold green]>>> 节点: {node.host}[/bold green]")

        # --- Step 1: 同步文件 ---
        # 将宿主机 A 的 all_in_one 完整克隆到 B (排除 log_buffer)
        if not node.sync_artifacts():
            continue

        # --- Step 2: 清理旧容器 ---
        node.run_cmd(f"docker rm -f {NEW_CONTAINER_NAME}")

        # --- Step 3: 启动容器 (空转待命) ---
        # 宿主机 path_B_root -> 容器 /app
        mount_arg = f"-v {node.path_B_root}:{CONTAINER_WORK_DIR}"

        # 命令解释：
        # --init: 僵尸进程回收
        # -it: 交互式终端 (保证容器启动后不退出)
        # -d: 后台运行
        # /bin/bash: 启动 bash 作为主进程
        docker_cmd = (
            f"docker run --init -it -d "
            f"--name {NEW_CONTAINER_NAME} "
            f"-w {CONTAINER_WORK_DIR} "
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
        # 假设 requirements2.txt 在 SISR 目录下，或者根目录下
        # 根据你之前的结构，这里尝试安装依赖
        console.print("   📦 正在安装依赖 (pip install)...")

        # 这里的路径取决于 requirements2.txt 实际在 all_in_one 下的位置
        # 假设在 SISR/requirements2.txt，如果是在根目录则去掉 SISR/
        # 我们先尝试找一下，或者你确定路径后修改这里
        req_cmd = "pip install -r SISR/requirements2.txt"

        # 使用 exec 在运行中的容器内执行命令
        ok_pip, res_pip = node.run_cmd(f"docker exec {NEW_CONTAINER_NAME} {req_cmd}")

        if ok_pip:
            console.print("   ✅ 环境配置完成")
        else:
            # 如果失败，可能是路径不对，不中断流程，但报个警
            console.print(f"   ⚠️  环境配置可能有误 (检查 requirements2.txt 路径): {res_pip}")

    # 3. 状态检查
    print_status(nodes)


def print_status(nodes):
    table = Table(title=f"容器状态: {NEW_CONTAINER_NAME}")
    table.add_column("IP", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Environment", style="yellow")

    for node in nodes:
        # 检查容器状态
        ok, out = node.run_cmd(f"docker ps -f name={NEW_CONTAINER_NAME} --format '{{{{.Status}}}}'")
        status = out if ok and out else "Not Found"

        # 简单检查 pip 是否安装成功 (检查 numpy)
        ok_env, _ = node.run_cmd(f"docker exec {NEW_CONTAINER_NAME} pip show numpy")
        env_status = "Ready" if ok_env else "Pip Failed"

        color = "green" if "Up" in status else "red"
        table.add_row(node.host, f"[{color}]{status}[/{color}]", env_status)

    console.print(table)


if __name__ == "__main__":
    main()