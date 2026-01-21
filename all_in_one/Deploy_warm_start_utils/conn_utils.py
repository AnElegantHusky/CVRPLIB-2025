import argparse
from fabric import Connection
from rich.console import Console
from rich.panel import Panel
from config import servers as SERVER_MANIFEST

console = Console()

# 默认服务器列表 (可以被覆盖)
DEFAULT_TARGETS = [
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


def run_dist_task(task_function, target_servers=None, task_name="Distributed Task"):
    """
    [核心驱动器]
    负责：遍历服务器 -> 建立连接 -> 将连接交给 task_function 执行具体逻辑

    Args:
        task_function: 一个函数，签名必须是 (conn, host_ip)
        target_servers: 目标服务器 IP 列表，如果为 None 则使用默认配置
    """
    targets = target_servers if target_servers else DEFAULT_TARGETS
    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in targets]

    console.rule(f"[bold blue]{task_name}[/bold blue]")

    for conf in active_nodes:
        host = conf['host']
        console.print(f"\n🔗 [bold]Connecting to {host}...[/bold]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # === 核心：把连接交给回调函数 ===
            task_function(conn, host)
            # ============================

            conn.close()

        except Exception as e:
            console.print(f"   [red]Connection/Task Error: {e}[/red]")

    console.rule("[bold blue]All Tasks Finished[/bold blue]")