import time
from rich.table import Table
from rich.console import Console
from fabric import Connection
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================
DOCKER_IMAGE = "cvrplib_sy5"
NEW_CONTAINER_NAME = "warm_start"

# 1. 容器内核心工作目录 (对应 warm_start_work_path)
CONTAINER_WORK_DIR = "/app"

# 2. 容器内与 CVRPLIB 交互的挂载点 (对应 main_work_path)
#    Warm_start 将从这里读 .db，并将 .json 投递到这里
CONTAINER_EXCHANGE_DIR = "/cvrplib_link"

# 定义要操作的服务器 IP
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


def main():
    console.rule(f"[bold blue]重新部署 {NEW_CONTAINER_NAME} (关联双路径)[/bold blue]")

    # 1. 筛选并连接服务器
    active_nodes = []
    for conf in SERVER_MANIFEST:
        if conf['host'] in to_run_servers:
            # 简单封装一下连接对象，不依赖复杂的 ServerNode 类，保持轻量
            try:
                conn = Connection(
                    host=conf['host'],
                    user=conf['user'],
                    port=conf.get('port', 22),
                    connect_kwargs={"password": conf['password']},
                    connect_timeout=5
                )
                # 将 config 数据绑定到 connection 对象上方便调用
                conn.custom_config = conf
                active_nodes.append(conn)
            except Exception as e:
                console.print(f"[red]连接失败 {conf['host']}: {e}[/red]")

    if not active_nodes:
        console.print("[yellow]⚠️  没有选中任何服务器，请检查 to_run_servers 列表[/yellow]")
        return

    # 2. 执行任务
    for conn in active_nodes:
        host = conn.host
        conf = conn.custom_config

        console.print(f"\n[bold green]>>> 节点: {host}[/bold green]")

        # --- 获取关键路径 ---
        host_ws_path = conf.get('warm_start_work_path')
        host_main_path = conf.get('main_work_path')

        if not host_ws_path or not host_main_path:
            console.print(
                f"[red]   ❌ 配置缺失: 请检查 config.py 中是否包含 warm_start_work_path 和 main_work_path[/red]")
            continue

        console.print(f"   📂 自身路径 (Host): [cyan]{host_ws_path}[/cyan] -> [yellow]/app[/yellow]")
        console.print(
            f"   📂 交互路径 (Host): [cyan]{host_main_path}[/cyan] -> [yellow]{CONTAINER_EXCHANGE_DIR}[/yellow]")

        # --- Step 1: 停止并清理旧容器 ---
        # 不需要文件同步，直接杀容器
        try:
            conn.run(f"docker rm -f {NEW_CONTAINER_NAME}", hide=True, warn=True)
            console.print(f"   🗑️  旧容器已移除")
        except Exception as e:
            console.print(f"   ⚠️  移除容器警告: {e}")

        # --- Step 2: 启动容器 (双挂载) ---
        # -v host_ws:/app  -> 代码运行地
        # -v host_main:/cvrplib_link -> 读写交互地
        docker_cmd = (
            f"docker run --init -it -d "
            f"--name {NEW_CONTAINER_NAME} "
            f"-w {CONTAINER_WORK_DIR} "
            f"-v {host_ws_path}:{CONTAINER_WORK_DIR} "
            f"-v {host_main_path}:{CONTAINER_EXCHANGE_DIR} "
            f"{DOCKER_IMAGE} "
            f"/bin/bash"
        )

        console.print(f"   🚀 启动容器...")
        res = conn.run(docker_cmd, warn=True, hide=True)

        if res.failed:
            console.print(f"   ❌ 启动失败: {res.stderr.strip()}")
            continue

        container_id = res.stdout.strip()[:12]
        console.print(f"   ✅ 容器运行中 (ID: {container_id})")

        # --- Step 3: 配置环境 ---
        # 注意：因为我们将 host_ws_path 直接挂载到了 /app，
        # 而 host_ws_path 在 config 中已经是 .../SISR/ 了
        # 所以 requirements2.txt 应该就在 /app 下面
        console.print("   📦 安装依赖 (pip install requirements2.txt)...")

        pip_cmd = f"docker exec {NEW_CONTAINER_NAME} pip install -r requirements2.txt"
        res_pip = conn.run(pip_cmd, warn=True, hide=True)

        if res_pip.ok:
            console.print("   ✅ 依赖安装完成")
        else:
            # 如果失败，可能是路径层级问题，打印出来排查
            console.print(f"   ⚠️  依赖安装失败: {res_pip.stderr.strip()[:100]}...")
            console.print("      (提示: 确认 requirements2.txt 是否在 warm_start_work_path 根目录下)")

    console.rule("[bold blue]部署结束[/bold blue]")


if __name__ == "__main__":
    main()