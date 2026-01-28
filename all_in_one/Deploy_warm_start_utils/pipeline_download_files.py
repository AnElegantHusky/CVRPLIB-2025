import os
import argparse
from pathlib import Path
from fabric import Connection
from rich.console import Console
from rich.progress import track

# 引入配置
from config import servers as SERVER_MANIFEST

console = Console()

# ================= 配置区域 =================

# 默认本地下载保存目录
DEFAULT_DOWNLOAD_DIR = Path("./downloaded_files")


# ================= 核心逻辑 =================

def get_remote_path(server_conf, location_type, file_name):
    """
    根据配置类型获取远程文件的完整路径
    """
    if location_type == "main":
        base_path = server_conf.get('main_work_path')
    elif location_type == "warm_start":
        # 如果 config 中没有定义 warm_start_work_path，通常默认与 main 相同
        base_path = server_conf.get('warm_start_work_path', server_conf.get('main_work_path'))
    else:
        raise ValueError(f"Unknown location type: {location_type}")

    if not base_path:
        raise ValueError(f"Base path for '{location_type}' not found in server config.")

    # 使用 Linux 路径分隔符 /
    return f"{base_path}/{file_name}".replace("//", "/")


def run_download_pipeline(target_filename, location_type, target_servers=None, local_dir=DEFAULT_DOWNLOAD_DIR):
    """
    执行文件下载流水线
    """
    console.rule(f"[bold blue]批量下载文件: {target_filename} (从 {location_type})[/bold blue]")

    # 1. 准备本地目录
    local_dir = Path(local_dir)
    local_dir.mkdir(parents=True, exist_ok=True)
    console.print(f"[cyan]📂 本地保存路径: {local_dir.resolve()}[/cyan]")

    # 2. 筛选目标服务器
    if target_servers is None:
        active_nodes = SERVER_MANIFEST
    else:
        active_nodes = [s for s in SERVER_MANIFEST if s['host'] in target_servers]
        if not active_nodes:
            console.print("[red]❌ 未找到匹配的服务器配置[/red]")
            return

    success_count = 0
    fail_count = 0

    # 3. 遍历下载
    for conf in active_nodes:
        host_ip = conf['host']
        user = conf['user']
        password = conf['password']
        port = conf.get('port', 22)

        # 提取 IP 第四段 (例如 10.90.91.100 -> 100)
        ip_suffix = host_ip.split('.')[-1]

        # 构造本地文件名: filename_100.log
        file_stem = Path(target_filename).stem
        file_ext = Path(target_filename).suffix
        local_filename = f"{file_stem}_{ip_suffix}{file_ext}"
        local_file_path = local_dir / local_filename

        try:
            # 获取远程完整路径
            remote_path = get_remote_path(conf, location_type, target_filename)

            console.print(f"   ⬇️  Connecting to [bold cyan]{host_ip}[/bold cyan]...")

            with Connection(host=host_ip, user=user, port=port, connect_kwargs={"password": password},
                            connect_timeout=5) as conn:
                # 检查文件是否存在
                # 使用 test -f 命令检查文件
                check_result = conn.run(f"test -f {remote_path}", warn=True, hide=True)

                if check_result.failed:
                    console.print(f"      [yellow]⚠️  File not found remote: {remote_path}[/yellow]")
                    fail_count += 1
                    continue

                # 执行下载
                conn.get(remote_path, str(local_file_path))
                console.print(f"      [green]✅ Saved to: {local_filename}[/green]")
                success_count += 1

        except Exception as e:
            console.print(f"      [red]❌ Error on {host_ip}: {e}[/red]")
            fail_count += 1

    console.rule("[bold blue]下载任务结束[/bold blue]")
    console.print(f"📊 成功: [green]{success_count}[/green] | 失败/未找到: [red]{fail_count}[/red]")


# ================= 主入口 =================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Batch download files from servers.")

    # 必须参数：文件名
    parser.add_argument("filename", type=str, help="远程文件名 (例如: guardian.log 或 result.csv)")

    # 可选参数：路径类型 (默认 main)
    parser.add_argument("--type", type=str, choices=["main", "warm_start"], default="main",
                        help="远程路径类型: 'main' 或 'warm_start' (默认为 main)")

    # 可选参数：指定服务器 IP
    parser.add_argument("--servers", nargs="+", help="指定服务器IP列表 (留空则拉取所有配置的服务器)")

    # 可选参数：保存路径
    parser.add_argument("--out", type=str, default=str(DEFAULT_DOWNLOAD_DIR), help="本地保存文件夹路径")

    args = parser.parse_args()

    # ================= 新增代码开始 =================
    # 1. 将字符串路径转换为 Path 对象
    output_path = Path(args.out)

    # 2. 检测并创建
    # parents=True : 允许创建多级目录 (相当于 mkdir -p)
    # exist_ok=True: 如果目录已经存在，不会报错 (如果不加这个，目录存在时会抛出异常)
    if not output_path.exists():
        output_path.mkdir(parents=True, exist_ok=True)
        console.print(f"[yellow]📂 检测到目录不存在，已自动创建: {output_path.resolve()}[/yellow]")
    # ================= 新增代码结束 =================

    run_download_pipeline(
        target_filename=args.filename,
        location_type=args.type,
        target_servers=args.servers,
        local_dir=args.out
    )