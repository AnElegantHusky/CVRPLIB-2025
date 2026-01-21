import argparse
import sys
from fabric import Connection
from rich.console import Console
from rich.panel import Panel
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================
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

CONTAINER_NAME = "cvrplib"
ANCHOR_FILE = "main_for_all_final.py"


def find_container_workdir(conn, container_name):
    # ... (保持原有的查找逻辑不变) ...
    try:
        find_cmd = (
            f"docker exec {container_name} "
            f"find /app -maxdepth 4 -name '{ANCHOR_FILE}' -print -quit 2>/dev/null"
        )
        result = conn.run(find_cmd, warn=True, hide=True)
        if result.ok and result.stdout.strip():
            full_path = result.stdout.strip()
            return "/".join(full_path.split("/")[:-1])

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
    console.rule(f"[bold blue]Docker 批量命令执行器 {mode_str}[/bold blue]")
    console.print(f"📦 Container: [bold cyan]{CONTAINER_NAME}[/bold cyan]")
    console.print(f"🚀 Command:   [bold yellow]{target_cmd}[/bold yellow]")

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

            # 1. 动态寻找路径
            work_dir = find_container_workdir(conn, CONTAINER_NAME)

            if not work_dir:
                console.print(f"   ❌ [red]Could not find SISR directory![/red]")
                conn.close()
                continue

            # 2. 构造命令
            # 核心修改：如果是后台模式，使用 docker exec -d
            docker_flags = "-d" if background else ""

            # 注意：后台模式下，必须把输出重定向写在命令里，否则日志就丢了
            # 我们在这里不强制加 nohup，因为 docker exec -d 已经接管了生命周期
            # 但加上 nohup 习惯上更保险，尤其是为了处理 SIGHUP

            full_docker_cmd = (
                f"docker exec {docker_flags} {CONTAINER_NAME} /bin/bash -c "
                f"\"cd {work_dir} && {target_cmd}\""
            )

            # 3. 执行
            result = conn.run(full_docker_cmd, warn=True, hide=True)

            if result.ok:
                if background:
                    console.print(f"   ✅ [green]Task dispatched to background[/green]")
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

    console.rule("[bold blue]Done[/bold blue]")


def exec_in_cvrplib(conn, cmd, background=False):
    """
    [纯逻辑函数]
    接收一个已建立的 conn，在 CVRPLIB 容器中执行命令
    """
    # 1. 找路径
    work_dir = find_container_workdir(conn, CONTAINER_NAME)
    if not work_dir:
        console.print(f"      ❌ [CVRPLIB] Workdir not found (Anchor: {ANCHOR_FILE})")
        return False

    # 2. 构造命令
    bg_flag = "-d" if background else ""
    full_cmd = f"docker exec {bg_flag} {CONTAINER_NAME} /bin/bash -c \"cd {work_dir} && {cmd}\""

    # 3. 执行
    console.print(f"      🚀 [CVRPLIB] Exec: [dim]{cmd}[/dim]")
    result = conn.run(full_cmd, warn=True, hide=True)

    if result.ok:
        console.print(f"      ✅ Success")
        return True
    else:
        console.print(f"      ❌ Failed: {result.stderr.strip()}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run command inside Docker SISR dir")
    parser.add_argument("cmd", type=str, help="The command to run")
    # 添加 --bg 参数
    parser.add_argument("--bg", action="store_true", help="Run in background (docker exec -d)")

    args = parser.parse_args()

    run_docker_cmd(args.cmd, background=args.bg)

    # python pipeline_docker_cmd.py --bg "nohup python -u service_ingest_sol.py > service_ingest.log 2>&1 &"