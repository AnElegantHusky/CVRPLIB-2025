# pipeline_upload_tools.py
import os
from fabric import Connection
from rich.console import Console
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================

# 1. 待上传文件列表
# 格式: (本地文件名, 目标标记)
# 目标标记可选: 'main' (CVRPLIB), 'warm_start', 'both'
FILES_TO_UPLOAD = [
    ("./files_to_upload/write_outer_sol.py", "main"),  # 基础库
    ("./files_to_upload/service_ingest_sol.py", "main"),  # 服务进程
    # ("your_warm_start_script.py", "warm_start"), # 如果有warm_start代码要更
]

# 2. 筛选服务器 (本次操作的机器)
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
    console.rule("[bold blue]工具上传与环境配置 Pipeline[/bold blue]")

    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]没有选中任何服务器。[/yellow]")
        return

    for conf in active_nodes:
        host = conf['host']
        console.print(f"\n[bold green]>>> 处理节点: {host}[/bold green]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # 获取路径配置
            main_path = conf.get('main_work_path')  # CVRPLIB 路径
            ws_path = conf.get('warm_start_work_path')  # Warm Start 路径

            if not main_path or not ws_path:
                console.print("[red]Config 缺少 main_work_path 或 warm_start_work_path[/red]")
                continue

            # --- Step 1: 创建共享文件夹 & 设置权限 ---
            # 在 main_work_path 下创建 outer_sol (SISR/outer_sol)
            # 也可以在 ws_path 下建软链，但最重要的是物理路径存在且权限为 777

            outer_sol_path = os.path.join(main_path, "outer_sol")
            console.print(f"   🛠️  配置共享目录: {outer_sol_path}")

            # -p 确保目录存在, chmod 777 确保两个容器都能写
            conn.run(f"mkdir -p {outer_sol_path}", hide=True)
            conn.run(f"chmod -R 777 {outer_sol_path}", hide=True)

            # --- Step 2: 上传文件 ---
            for local_file, target_type in FILES_TO_UPLOAD:
                if not os.path.exists(local_file):
                    console.print(f"[red]   [跳过] 本地文件不存在: {local_file}[/red]")
                    continue

                targets = []
                if target_type in ['main', 'both']:
                    targets.append(main_path)
                if target_type in ['warm_start', 'both']:
                    targets.append(ws_path)

                for dest_dir in targets:
                    remote_path = os.path.join(dest_dir, local_file)
                    console.print(f"   ⬆️  上传 {local_file} -> {target_type} ({dest_dir})")
                    conn.put(local_file, remote=remote_path)

            console.print("   ✅ 节点完成")
            conn.close()

        except Exception as e:
            console.print(f"[red]   连接或执行出错: {e}[/red]")

    console.rule("[bold blue]全部完成[/bold blue]")


if __name__ == "__main__":
    main()