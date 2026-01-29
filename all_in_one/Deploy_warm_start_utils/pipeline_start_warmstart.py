from rich.console import Console
from rich.panel import Panel
import time

# 1. 引入驱动器 (负责连接)
# 假设你已经把 pipeline_cmd 重命名为 conn_utils
from conn_utils import run_dist_task
from pipeline_upload_files import run_upload_pipeline

# 2. 引入工具库 (负责容器内操作)
from pipeline_docker_cvrplib_cmd import exec_in_cvrplib, CONTAINER_NAME as CVRP_NAME
from pipeline_docker_warmstart_cmd import exec_in_warmstart, CONTAINER_NAME as WS_NAME

console = Console()


SERVICE_INGEST_SCRIPT = "service_ingest_sol.py"
SERVICE_INGEST_LOG = "service_ingest_redirect.log"

GUARDIAN_SCRIPT = "guardian.py"
GUARDIAN_LOG = "guardian.log"


def task_ensure_containers_up(conn, host_ip):
    """
    这一步只负责：检查容器 -> 如果死掉就启动。
    绝对不运行 exec_in_warmstart，只在宿主机 Shell 运行 docker 命令。
    """
    console.print(f"🏥 Health Check on {host_ip}...")

    # 我们要检查的容器列表
    target_containers = [WS_NAME]

    for container in target_containers:
        # 1. 检查状态
        check_cmd = f"docker inspect -f '{{{{.State.Running}}}}' {container}"
        res = conn.run(check_cmd, warn=True, hide=True)

        is_running = res.ok and res.stdout.strip().lower() == 'true'

        if is_running:
            console.print(f"   ✅ Container {container} is running.")
        else:
            console.print(f"   ⚠️ Container {container} is STOPPED. Starting...")
            # 2. 启动容器
            start_res = conn.run(f"docker start {container}", warn=True, hide=True)

            if start_res.ok:
                console.print(f"      ✅ Started successfully. Waiting 5s for OS boot...")
                time.sleep(5)  # 给容器内 Linux 启动的时间
            else:
                console.print(f"      ❌ Failed to start {container}! {start_res.stderr}")
                raise Exception(f"Container {container} failed to start on {host_ip}")

# === 核心业务逻辑 ===

def restart_ingest_service(conn, container_name):
    """
    安全重启 service_ingest_sol.py
    策略：Send SIGTERM -> Wait -> Force Kill if stuck -> Start
    """
    console.print(f"   🔄 [Ingest] Restarting {SERVICE_INGEST_SCRIPT}...")

    # 1. 尝试优雅停止 (pkill 默认发送 SIGTERM，Python脚本捕获后会安全退出)
    # -f 匹配完整命令行，确保不杀错 main_for_all
    stop_cmd = f"pkill -f {SERVICE_INGEST_SCRIPT}"

    # 我们先检查有没有在跑
    check_cmd = f"pgrep -f {SERVICE_INGEST_SCRIPT}"
    if conn.run(f"docker exec {container_name} {check_cmd}", warn=True, hide=True).ok:
        console.print("      ⚠️  Found running process. Stopping safely...")
        exec_in_cvrplib(conn, stop_cmd)

        # 等待 3 秒让它把 DB 写完
        time.sleep(3)

        # 再次检查，如果还没死，强制杀掉 (避免脚本卡死)
        if conn.run(f"docker exec {container_name} {check_cmd}", warn=True, hide=True).ok:
            console.print("      ⚠️  Process stuck. Force killing...")
            exec_in_cvrplib(conn, f"pkill -9 -f {SERVICE_INGEST_SCRIPT}")
        else:
            console.print("      ✅ Stopped gracefully.")
    else:
        console.print("      ✅ No old process found.")

    # 2. 启动新进程
    start_cmd = (
        f"nohup python3 -u {SERVICE_INGEST_SCRIPT} "
        f"> {SERVICE_INGEST_LOG} 2>&1 &"
    )
    exec_in_cvrplib(conn, start_cmd, background=True)


def restart_guardian_service(conn, container_name):
    """
    重启 guardian.py (逻辑同上，比较简单，直接杀也没事，因为 guardian 是读操作为主)
    """
    console.print(f"   🛡️ [Guardian] Restarting {GUARDIAN_SCRIPT}...")

    # 1. 停止旧进程
    stop_cmd = f"pkill -f {GUARDIAN_SCRIPT}"
    exec_in_warmstart(conn, stop_cmd)
    # 稍微等一下
    time.sleep(1)

    # 2. 启动新进程
    start_cmd = (
        f"nohup python3 -u {GUARDIAN_SCRIPT} "
        f"> {GUARDIAN_LOG} 2>&1 &"
    )
    exec_in_warmstart(conn, start_cmd, background=True)


def my_startup_logic(conn, host_ip):
    """
    原子业务流程：在单台服务器上执行
    """
    console.print(Panel(f"Starting Services on {host_ip}", style="cyan"))

    # 1. 启动/重启 Ingest Service (CVRPLIB 容器)
    #    注意：这里自带了“检查-杀进程-启动”的完整逻辑
    restart_ingest_service(conn, CVRP_NAME)

    # 2. 启动/重启 Guardian (WarmStart 容器)
    # restart_guardian_service(conn, WS_NAME)


# === 入口 ===
if __name__ == "__main__":

    # # 传输必要文件
    MY_FILES = [
        # ("./files_to_upload/extract_survivor_history.py", "both"),
        ("./files_to_upload/guardian.py", "warm_start"),
        ("./files_to_upload/main_for_all_warm_start.py", "warm_start"),
        ("./files_to_upload/service_ingest_sol.py", "main"),
        # ("./files_to_upload/write_outer_sol.py", "both"),
        # ("./files_to_upload/main_for_all_restart.py", "main"),
        # ("./files_to_upload/test_extract.py", "warm_start"),
    ]

    TARGET_SERVERS = [
        # "10.90.91.100",
        # "10.90.91.101",
        # "10.90.91.124",
        # "10.90.91.125",
        # "10.90.91.126",
        # "10.90.91.127",
        # "10.90.91.163",
        # "10.90.91.167",
        # "10.90.91.49",
        # "10.90.91.51",
        # "10.90.91.231",
        "10.90.91.232",
    ]

    run_upload_pipeline(MY_FILES, target_servers=TARGET_SERVERS)

    run_dist_task(task_ensure_containers_up, target_servers=TARGET_SERVERS)

    run_dist_task(my_startup_logic, target_servers=TARGET_SERVERS)