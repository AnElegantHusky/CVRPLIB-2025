import argparse
import sys
from fabric import Connection
from rich.console import Console
from rich.panel import Panel
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================
# 1. 目标服务器列表
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

# 2. 容器名称 (运行算法/Guardian 的那个容器)
CONTAINER_NAME = "warm_start"

# 3. 路径锚点文件 (用来确认我们找到了正确的工作目录)
# 我们会寻找包含这个文件的目录
ANCHOR_FILE = "guardian.py"


def find_container_workdir(conn, container_name):
    """
    在容器内部动态查找工作目录。
    """
    try:
        # 1. 尝试在 /app 目录下查找锚点文件
        find_cmd = (
            f"docker exec {container_name} "
            f"find /app -maxdepth 4 -name '{ANCHOR_FILE}' -print -quit 2>/dev/null"
        )

        result = conn.run(find_cmd, warn=True, hide=True)

        if result.ok and result.stdout.strip():
            full_path = result.stdout.strip()
            return "/".join(full_path.split("/")[:-1])

        # 2. 备选方案：尝试找 /home
        find_cmd_backup = (
            f"docker exec {container_name} "
            f"find /home -maxdepth 4 -name '{ANCHOR_FILE}' -print -quit 2>/dev/null"
        )
        result_bk = conn.run(find_cmd_backup, warn=True, hide=True)

        if result_bk.ok and result_bk.stdout.strip():
            full_path = result_bk.stdout.strip()
            return "/".join(full_path.split("/")[:-1])

    except Exception as e:
        console.print(f"[red]   [Find Error] {e}[/red]")

    return None


def run_docker_cmd(target_cmd, background=False):
    mode_str = "[BACKGROUND TASK]" if background else "[INTERACTIVE]"
    console.rule(f"[bold magenta]WarmStart 容器控制台 {mode_str}[/bold magenta]")
    console.print(f"📦 Container: [bold cyan]{CONTAINER_NAME}[/bold cyan]")
    console.print(f"🚀 Command:   [bold yellow]{target_cmd}[/bold yellow]")
    console.print(f"🔍 Anchor:    Finding path via '{ANCHOR_FILE}'\n")

    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    for conf in active_nodes:
        host = conf['host']
        console.print(f"🔗 [bold]Connecting to {host}...[/bold]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # --- Step 1: 动态寻找路径 ---
            work_dir = find_container_workdir(conn, CONTAINER_NAME)

            if not work_dir:
                console.print(f"   ❌ [red]Could not find '{ANCHOR_FILE}' inside container![/red]")
                conn.close()
                continue

            # --- Step 2: 构造命令 ---
            # 如果是后台模式，使用 docker exec -d
            docker_flags = "-d" if background else ""

            # 构造完整命令：进入目录 -> 执行命令
            full_docker_cmd = (
                f"docker exec {docker_flags} {CONTAINER_NAME} /bin/bash -c "
                f"\"cd {work_dir} && {target_cmd}\""
            )

            # --- Step 3: 执行 ---
            result = conn.run(full_docker_cmd, warn=True, hide=True)

            if result.ok:
                if background:
                    console.print(f"   ✅ [green]Guardian dispatched to background[/green]")
                    console.print(f"      (Check logs manually inside container)")
                else:
                    console.print(f"   ✅ [green]Success[/green]")
                    if result.stdout.strip():
                        console.print(Panel(result.stdout.strip(), title=f"Output {host}", border_style="green"))
            else:
                console.print(f"   ❌ [red]Failed (Exit Code {result.exited})[/red]")
                if result.stderr.strip():
                    console.print(f"      Error: {result.stderr.strip()}")

            conn.close()

        except Exception as e:
            console.print(f"   [red]Connection Error: {e}[/red]")

    console.rule("[bold magenta]Done[/bold magenta]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run command inside WarmStart Docker")
    parser.add_argument("cmd", type=str, help="The command to run")
    parser.add_argument("--bg", action="store_true", help="Run in background (docker exec -d)")

    args = parser.parse_args()

    run_docker_cmd(args.cmd, background=args.bg)

    # python pipeline_docker_warmstart_cmd.py --bg "nohup python -u guardian.py > guardian.log 2>&1 &"