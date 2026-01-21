import argparse
from fabric import Connection
from rich.console import Console
from config import servers as SERVER_MANIFEST
from typing import List

console = Console()

# ================= 配置区域 =================
# 筛选要执行命令的服务器 IP
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


def execute_batch_command(command_str: str, target_scope: str = "main", to_run_servers: List | None = None):
    """
    Args:
        command_str: 要执行的 shell 命令 (例如 "ls -la" 或 "chmod 777 folder")
        target_scope: 目标路径选择 ("main", "warm_start", "both")
    """
    console.rule(f"[bold blue]批量命令执行工具[/bold blue]")
    console.print(f"指令: [yellow]{command_str}[/yellow]")
    console.print(f"范围: [cyan]{target_scope}[/cyan]")

    # 1. 筛选服务器
    if to_run_servers is None:
        active_nodes = [s for s in SERVER_MANIFEST]
    else:
        active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]⚠️  没有选中任何服务器，请检查 to_run_servers 列表[/yellow]")
        return

    for conf in active_nodes:
        host = conf['host']
        console.print(f"\n[bold green]>>> 节点: {host}[/bold green]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # 2. 解析需要执行的路径列表
            target_paths = []

            # 获取 config 中的路径
            path_main = conf.get('main_work_path')
            path_ws = conf.get('warm_start_work_path')

            if target_scope in ['main', 'both']:
                if path_main:
                    target_paths.append(("Main (CVRPLIB)", path_main))
                else:
                    console.print("[red]   ❌ Config 缺失 main_work_path[/red]")

            if target_scope in ['warm_start', 'both']:
                if path_ws:
                    target_paths.append(("Warm Start", path_ws))
                else:
                    console.print("[red]   ❌ Config 缺失 warm_start_work_path[/red]")

            # 3. 在每个路径下执行命令
            for label, work_dir in target_paths:
                console.print(f"   📂 进入目录 [{label}]: {work_dir}")

                # 组合命令：进入目录 && 执行命令
                # 使用 'cd {dir} && {cmd}' 确保在正确目录下执行
                full_cmd = f"cd {work_dir} && {command_str}"

                result = conn.run(full_cmd, warn=True, hide=True)

                if result.ok:
                    console.print(f"      ✅ 执行成功")
                    # 如果有输出且不长，可以打印出来
                    if result.stdout.strip():
                        console.print(f"      [dim]{result.stdout.strip()}[/dim]")
                else:
                    console.print(f"      ❌ 执行失败: {result.stderr.strip()}")

            conn.close()

        except Exception as e:
            console.print(f"[red]   连接或未知错误: {e}[/red]")

    console.rule("[bold blue]任务结束[/bold blue]")


if __name__ == "__main__":
    # ================= 使用示例 =================

    # 场景 1: 创建多来源的解文件夹，并赋予 777 权限
    # 注意：根据之前的逻辑，这些文件夹物理上位于 CVRPLIB 的目录下 (main_work_path)
    # Warm_start 容器是通过挂载读取它们的，所以只需要在 main 下操作即可。

    CMD_CREATE_DIRS = "mkdir -p warm_start_outer_sol mahdi_outer_sol"
    CMD_CHMOD_DIRS = "chmod -R 777 warm_start_outer_sol mahdi_outer_sol"

    # 组合一下，一次执行完
    MY_COMMAND = f"{CMD_CREATE_DIRS} && {CMD_CHMOD_DIRS}"

    # scope 可选:
    #   'main'       -> 只在 main_work_path 执行 (推荐，用于操作共享数据)
    #   'warm_start' -> 只在 warm_start_work_path 执行 (用于操作代码/配置)
    #   'both'       -> 两个地方都执行

    execute_batch_command(
        command_str=MY_COMMAND,
        target_scope="warm_start"
    )

    # 场景 2: 比如你想查看某个文件是否存在
    # execute_batch_command("ls -l service_ingest_sol.py", "main")