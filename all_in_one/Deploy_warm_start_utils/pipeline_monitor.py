import os
import datetime
from fabric import Connection
from rich.console import Console
from rich.table import Table
from rich import box
from config import servers as SERVER_MANIFEST

# 初始化 Console，开启录制功能以便导出文件
console = Console(record=True)

# ================= 配置区域 =================
# 结果保存目录
LOG_DIR = "logs_monitor"

# 筛选要监控的服务器 (空列表代表监控 config.py 中的所有服务器)
TARGET_SERVERS = [
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

# 进程名定义 (根据您的要求配置)
PROC_CVRP_INGEST = "service_ingest_sol.py"
PROC_CVRP_MAIN = "main_for_all"  # 匹配 main_for_all_final.py 等
PROC_WS_GUARD = "guardian.py"
PROC_WS_MAIN = "main_for_all_warm_start"  # 匹配您要求的特定进程名


def get_targets():
    """获取目标服务器列表"""
    if not TARGET_SERVERS:
        return SERVER_MANIFEST
    return [s for s in SERVER_MANIFEST if s['host'] in TARGET_SERVERS]


def ensure_log_dir():
    """确保日志目录存在"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)


def get_host_stats(conn):
    """
    获取宿主机资源状态
    返回: dict 或 None
    """
    try:
        # 组合命令: 核心数, 负载, 内存信息
        # free -m 输出第二行通常是 Mem: total used free shared buff/cache available
        # 我们取 Total($2) 和 Available($7)
        cmd = (
            "echo 'CORE:'$(nproc) && "
            "cat /proc/loadavg | awk '{print \"LOAD:\"$1}' && "
            "free -m | awk 'NR==2{printf \"MEM_TOTAL:%s\\nMEM_AVAIL:%s\", $2, $7}'"
        )
        result = conn.run(cmd, warn=True, hide=True, timeout=5)
        if not result.ok:
            return None

        stats = {}
        for line in result.stdout.strip().split('\n'):
            if ':' in line:
                k, v = line.split(':', 1)
                stats[k] = float(v)

        # 计算逻辑
        total_cores = int(stats.get('CORE', 1))
        load_1min = stats.get('LOAD', 0)
        # 可用核数 = 总核 - 负载 (如果负载大于核数则为0)
        avail_cores = max(0, total_cores - load_1min)

        mem_total = stats.get('MEM_TOTAL', 1)
        mem_avail = stats.get('MEM_AVAIL', 0)
        mem_used = mem_total - mem_avail
        mem_pct = (mem_used / mem_total) * 100

        return {
            "cores_total": total_cores,
            "cores_avail": avail_cores,
            "load": load_1min,
            "mem_total_gb": mem_total / 1024,
            "mem_used_gb": mem_used / 1024,
            "mem_pct": mem_pct
        }
    except Exception:
        return None


def check_docker_process(conn, container_name, process_keyword, mode="count"):
    """
    检查容器内进程
    mode="count": 返回进程数量 (int)
    mode="bool": 返回是否运行 (bool)
    """
    try:
        # 1. 先检查容器是否存活
        check_cont = conn.run(f"docker inspect -f '{{{{.State.Running}}}}' {container_name}", warn=True, hide=True)
        if not check_cont.ok or check_cont.stdout.strip() != 'true':
            return -1  # 容器挂了

        # 2. 检查进程 (grep -v grep 是关键)
        # 使用 ps -ef | grep 'key' | grep -v grep | wc -l
        cmd = f"docker exec {container_name} bash -c \"ps -ef | grep '{process_keyword}' | grep -v grep | wc -l\""
        result = conn.run(cmd, warn=True, hide=True)

        if result.ok:
            count = int(result.stdout.strip())
            if mode == "bool":
                return 1 if count > 0 else 0
            return count
        return 0
    except Exception:
        return -1  # 异常视为容器不可达


def generate_report():
    ensure_log_dir()
    targets = get_targets()
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 创建表格
    table = Table(title=f"🚀 服务器集群监控报告 ({current_time})", box=box.ROUNDED)

    # 定义列
    table.add_column("Host IP", style="cyan bold", no_wrap=True)
    table.add_column("Host CPU\n(Avail / Total)", justify="right")
    table.add_column("Host Mem\n(Used / Total)", justify="right")

    # CVRPLIB
    table.add_column("CVRPLIB\nIngest", justify="center")  # Bool
    table.add_column("CVRPLIB\nMain(N)", justify="center")  # Count

    # WarmStart
    table.add_column("WarmStart\nGuardian", justify="center")  # Bool
    table.add_column("WarmStart\nMain(N)", justify="center")  # Count

    console.print(f"[yellow]开始扫描 {len(targets)} 台服务器...[/yellow]")

    for conf in targets:
        host = conf['host']
        row = [host]

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=3
            )

            # --- 1. Host Stats ---
            h_stats = get_host_stats(conn)
            if h_stats:
                # CPU: 可用 / 总量
                c_avail = h_stats['cores_avail']
                c_total = h_stats['cores_total']
                c_style = "red" if c_avail < 1 else "green"
                row.append(f"[{c_style}]{c_avail:.1f}[/] / {c_total}")

                # Mem: 已用 / 总量 (百分比)
                m_used = h_stats['mem_used_gb']
                m_total = h_stats['mem_total_gb']
                m_pct = h_stats['mem_pct']
                m_style = "red" if m_pct > 90 else ("yellow" if m_pct > 80 else "green")
                row.append(f"[{m_style}]{m_used:.1f}G / {m_total:.1f}G\n({m_pct:.0f}%)[/]")
            else:
                row.append("[red]Stats Fail[/]")
                row.append("-")

            if h_stats:  # 只有主机连接成功才查 Docker
                # --- 2. CVRPLIB ---
                # ingest (bool)
                c_ingest = check_docker_process(conn, "cvrplib", PROC_CVRP_INGEST, "bool")
                # main (count)
                c_main = check_docker_process(conn, "cvrplib", PROC_CVRP_MAIN, "count")

                # Format CVRPLIB
                if c_ingest == -1:
                    row.append("[dim red]Container Down[/]")
                    row.append("-")
                else:
                    row.append("[green]RUN[/]" if c_ingest else "[red]STOP[/]")
                    row.append(f"[bold]{c_main}[/]" if c_main > 0 else "[dim]0[/]")

                # --- 3. WarmStart ---
                # guardian (bool)
                w_guard = check_docker_process(conn, "warm_start", PROC_WS_GUARD, "bool")
                # main (count)
                w_main = check_docker_process(conn, "warm_start", PROC_WS_MAIN, "count")

                # Format WarmStart
                if w_guard == -1:
                    row.append("[dim red]Container Down[/]")
                    row.append("-")
                else:
                    row.append("[green]RUN[/]" if w_guard else "[red]STOP[/]")
                    row.append(f"[bold]{w_main}[/]" if w_main > 0 else "[dim]0[/]")

            else:
                # Host failed
                row.extend(["-", "-", "-", "-"])

            conn.close()
            table.add_row(*row)
            # 添加分割线 (可选)
            # table.add_section()

        except Exception as e:
            row.extend([f"[red bold]OFFLINE[/] ({str(e)[:10]}..)", "-", "-", "-", "-", "-"])
            table.add_row(*row)

    # 1. 打印到控制台
    console.print(table)

    # 2. 保存到本地文件
    file_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = os.path.join(LOG_DIR, f"monitor_report_{file_time}.txt")

    # save_text 会自动去除颜色代码，生成纯文本表格
    console.save_text(log_filename)

    console.print(f"\n[bold green]✅ 报告已保存至: {log_filename}[/bold green]")


if __name__ == "__main__":
    generate_report()