import os
from typing import List, Tuple, Optional
from fabric import Connection
from rich.console import Console
from config import servers as SERVER_MANIFEST

console = Console()

def run_upload_pipeline(files_to_upload: List[Tuple[str, str]], target_servers: Optional[List[str]] = None):
    """
    执行文件上传流水线。

    Args:
        files_to_upload: (本地路径, 目标标记) 的元组列表。
                         目标标记支持: "main", "warm_start", "both"。
        target_servers: 目标服务器IP列表。如果为 None，则上传到 SERVER_MANIFEST 中的所有服务器。
    """
    console.rule("[bold blue]通用文件上传 Pipeline[/bold blue]")

    # 1. 检查本地文件是否存在，避免连上服务器才报错
    # 逻辑保持不变：只要有一个文件不存在，立即停止
    for local_path, _ in files_to_upload:
        if not os.path.exists(local_path):
            console.print(f"[bold red]❌ 错误: 本地文件未找到 -> {local_path}[/bold red]")
            return

    # 2. 筛选目标服务器
    if target_servers is None:
        # 如果未指定，则选中所有 Config 中的服务器
        active_nodes = SERVER_MANIFEST
        console.print("[cyan]ℹ️  未指定 target_servers，将对所有配置节点执行操作。[/cyan]")
    else:
        # 按照 IP 筛选
        active_nodes = [s for s in SERVER_MANIFEST if s['host'] in target_servers]

    if not active_nodes:
        console.print("[yellow]⚠️  没有匹配到任何服务器，请检查 target_servers 或 config 配置[/yellow]")
        return

    # 3. 遍历服务器执行上传
    for conf in active_nodes:
        host = conf['host']
        console.print(f"\n[bold green]>>> 正在同步节点: {host}[/bold green]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # 获取远程基础路径
            path_map = {
                "main": conf.get('main_work_path'),
                "warm_start": conf.get('warm_start_work_path')
            }

            # 检查路径配置
            if not path_map["main"]:
                console.print("[yellow]   ⚠️  Config 缺失 main_work_path[/yellow]")
            if not path_map["warm_start"]:
                console.print("[yellow]   ⚠️  Config 缺失 warm_start_work_path[/yellow]")

            # 开始上传循环
            for local_path, target_tag in files_to_upload:
                # 3.1 确定文件名 (自动去除本地目录前缀)
                file_name = os.path.basename(local_path)

                # 3.2 确定目标路径列表
                dest_dirs = []

                if target_tag == "both":
                    if path_map["main"]: dest_dirs.append(path_map["main"])
                    if path_map["warm_start"]: dest_dirs.append(path_map["warm_start"])
                elif target_tag in path_map:
                    if path_map[target_tag]:
                        dest_dirs.append(path_map[target_tag])
                    else:
                        console.print(f"[red]   跳过 {file_name}: 目标 {target_tag} 路径未配置[/red]")
                else:
                    console.print(f"[red]   跳过 {file_name}: 未知的标记 '{target_tag}'[/red]")
                    continue

                # 3.3 执行上传
                for remote_dir in dest_dirs:
                    # 注意：如果本地是 Windows 且远程是 Linux，os.path.join 可能会使用反斜杠。
                    # Fabric 通常能处理，但如果遇到路径问题，可能需要改为 posixpath.join
                    remote_full_path = os.path.join(remote_dir, file_name)
                    console.print(f"   ⬆️  {local_path} -> [cyan]{remote_dir}[/cyan]")

                    try:
                        conn.put(local_path, remote=remote_full_path)
                    except Exception as e:
                        console.print(f"[red]      上传失败: {e}[/red]")

            conn.close()

        except Exception as e:
            console.print(f"[red]   连接错误: {e}[/red]")

    console.rule("[bold blue]上传任务结束[/bold blue]")


# ================= 使用示例 =================

if __name__ == "__main__":
    # 1. 定义待上传文件列表
    # 格式: (本地文件路径, 目标标记: "main" | "warm_start" | "both")
    MY_FILES = [
        ("./files_to_upload/extract_survivor_history.py", "both"),
        ("./files_to_upload/guardian.py", "warm_start"),
        ("./files_to_upload/main_for_all_warm_start.py", "warm_start"),
        ("./files_to_upload/service_ingest_sol.py", "main"),
        ("./files_to_upload/write_outer_sol.py", "both"),
        ("./files_to_upload/main_for_all_restart.py", "main"),
    ]

    # 2. 定义目标服务器 (None 表示全部)
    MY_SERVERS = [
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

    # 3. 调用函数
    # 场景 A: 传给指定服务器
    run_upload_pipeline(MY_FILES, target_servers=MY_SERVERS)

    # 场景 B: 传给所有配置中的服务器 (取消注释以使用)
    # run_upload_pipeline(MY_FILES, target_servers=None)