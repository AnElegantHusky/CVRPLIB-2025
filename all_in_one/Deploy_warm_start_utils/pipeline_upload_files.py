import os
import argparse
from fabric import Connection
from rich.console import Console
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 核心配置区域 =================

# 1. 待上传文件列表
# 格式: (本地文件路径, 目标标记)
#   - 本地路径: 支持相对路径 (e.g., "src/guardian.py") 或绝对路径。
#   - 目标标记: "main" (CVRPLIB目录), "warm_start" (算法目录), "both" (两者都传)
FILES_TO_UPLOAD = [
    # --- 示例 ---
    # ("write_outer_sol.py",    "main"),         # 只更新 CVRPLIB 的基础库
    # ("service_ingest_sol.py", "main"),         # 更新吸入服务
    # ("guardian.py",           "warm_start"),   # 更新 Warm Start 的守护进程
    # ("utils/config_loader.py", "both"),        # 更新两边都用的工具

    # 在这里填写你当前要传的文件:
    ("write_outer_sol.py", "both"),
    ("service_ingest_sol.py", "main"),
]

# 2. 目标服务器筛选
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


# ===========================================

def main():
    console.rule("[bold blue]通用文件上传 Pipeline[/bold blue]")

    # 检查本地文件是否存在，避免连上服务器才报错
    for local_path, _ in FILES_TO_UPLOAD:
        if not os.path.exists(local_path):
            console.print(f"[bold red]❌ 错误: 本地文件未找到 -> {local_path}[/bold red]")
            return

    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]⚠️  没有选中任何服务器，请检查 to_run_servers[/yellow]")
        return

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
            for local_path, target_tag in FILES_TO_UPLOAD:
                # 1. 确定文件名 (自动去除本地目录前缀)
                file_name = os.path.basename(local_path)

                # 2. 确定目标路径列表
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

                # 3. 执行上传
                for remote_dir in dest_dirs:
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


if __name__ == "__main__":
    main()