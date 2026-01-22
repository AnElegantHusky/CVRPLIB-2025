import sys
from rich.console import Console
from rich.panel import Panel

# 引入你的基础库
from conn_utils import run_dist_task
from config import servers as SERVER_MANIFEST
from pipeline_docker_warmstart_cmd import exec_in_warmstart

console = Console()


def kill_process_logic(conn, host_ip):
    """
    完全复刻 server_send_kill.py 的逻辑：
    按顺序逐个发送 pkill 命令。
    """
    console.print(Panel(f"🔪 Killing WarmStart Processes on {host_ip}", style="red"))

    # === 查杀清单 (顺序至关重要) ===
    # 格式: (进程关键字, 描述)
    kill_sequence = [
        # 1. 先杀 Guardian (总管)
        # 必须先杀它，防止它检测到子进程死亡后立即重启它们
        ("guardian.py", "Guardian (Manager)"),

        # 2. 再杀 Python Workers (中间层)
        ("main_for_all", "Python Workers"),

        ("python", "Python Processes"),

        # 3. 最后杀 Java (底层计算)
        ("java", "Java Solvers"),
    ]

    for target, desc in kill_sequence:
        console.print(f"   -> Killing {desc} ({target})...")

        # 构造命令: pkill -9 -f <target> || true
        # 解释:
        #   -9: 强制杀死
        #   -f: 匹配完整命令行 (防止只匹配到 python 而没匹配到脚本名)
        #   || true: 即使进程不存在 (pkill返回1)，也不报错，保证脚本继续向下执行
        cmd = f"pkill -9 -f '{target}' || true"

        # 使用现有的 exec_in_warmstart 工具发送命令
        # 这会自动处理 cd 到工作目录等逻辑，虽然 pkill 不需要目录，但这保持了 pipeline 的统一性
        exec_in_warmstart(conn, cmd, background=False)

    # === 验证环节 ===
    console.print(f"   🔍 Verifying cleanup...")
    # 检查残留
    verify_cmd = "ps aux | grep -E 'guardian|main_for_all|java' | grep -v grep"

    # 我们直接执行 verify_cmd，exec_in_warmstart 会把输出打印在控制台
    # 如果输出为空，说明杀干净了；如果有输出，你会直接看到残留的进程
    exec_in_warmstart(conn, verify_cmd, background=False)

    console.print(f"   ✅ Kill sequence finished on {host_ip}.")

if __name__ == "__main__":
    from pipeline_upload_files import run_upload_pipeline

    # 格式: (本地文件路径, 目标标记: "main" | "warm_start" | "both")
    MY_FILES = [
        ("./files_to_upload/collect_sols.py", "main"),
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

    run_dist_task(kill_process_logic, target_servers=TARGET_SERVERS)