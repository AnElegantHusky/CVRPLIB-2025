from rich.console import Console
from rich.panel import Panel

# 1. 引入驱动器 (负责连接)
from conn_utils import run_dist_task

# 2. 引入工具库 (负责容器内操作)
from pipeline_docker_cvrplib_cmd import exec_in_cvrplib, CONTAINER_NAME as CVRP_NAME
from pipeline_docker_warmstart_cmd import exec_in_warmstart, CONTAINER_NAME as WS_NAME
from pipeline_upload_files import run_upload_pipeline

console = Console()

# === 配置 ===

RESTART_SCRIPT = "main_for_all_restart.py"
LOG_FILE = "restart_process.log"


# === 辅助：通用检查函数 (因为这个逻辑太通用，没放在特定容器库里) ===
def ensure_container_alive(conn, container_name):
    """如果容器死了，就把它救活"""
    check_cmd = f"docker inspect -f '{{{{.State.Running}}}}' {container_name}"
    res = conn.run(check_cmd, warn=True, hide=True)

    if res.ok and res.stdout.strip().lower() == 'true':
        console.print(f"      ✅ [Check] {container_name} is running")
        return True
    else:
        console.print(f"      ⚠️ [Check] {container_name} is STOPPED. Starting...")
        start_res = conn.run(f"docker start {container_name}", warn=True, hide=True)
        if start_res.ok:
            console.print(f"      ✅ Started {container_name}")
            return True
        else:
            console.print(f"      ❌ Failed to start {container_name}")
            return False


# === 核心业务逻辑 (回调函数) ===
def restart_logic(conn, host_ip):
    """
    这就是我们要执行的原子业务流程。
    conn 已经由 pipeline_cmd 连好了，直接用！
    """
    console.print(Panel(f"Executing Restart Sequence on {host_ip}", style="cyan"))

    # Step 1: 确保基础设施存活
    cvrp_ok = ensure_container_alive(conn, CVRP_NAME)
    ws_ok = ensure_container_alive(conn, WS_NAME)

    if not (cvrp_ok and ws_ok):
        console.print("      ❌ Infrastructure check failed. Aborting restart.")
        return

    # Step 2: 发送重启指令 (复用 pipeline_docker_cvrplib_cmd 的能力)
    # 构造后台命令
    cmd = f"nohup python3 -u {RESTART_SCRIPT} > {LOG_FILE} 2>&1 &"

    console.print("      🔄 Triggering restart script...")
    exec_in_cvrplib(conn, cmd, background=True)


# === 入口 ===
if __name__ == "__main__":

    # # 传输必要文件
    # MY_FILES = [
    #     ("./files_to_upload/extract_survivor_history.py", "both"),
    #     ("./files_to_upload/guardian.py", "warm_start"),
    #     ("./files_to_upload/main_for_all_warm_start.py", "warm_start"),
    #     ("./files_to_upload/service_ingest_sol.py", "main"),
    #     ("./files_to_upload/write_outer_sol.py", "both"),
    #     ("./files_to_upload/main_for_all_restart.py", "main"),
    # ]
    #
    # ALL_SERVERS = [
    #     "10.90.91.100",
    #     "10.90.91.101",
    #     "10.90.91.124",
    #     "10.90.91.125",
    #     "10.90.91.126",
    #     "10.90.91.127",
    #     "10.90.91.163",
    #     "10.90.91.167",
    #     "10.90.91.49",
    #     "10.90.91.51",
    #     "10.90.91.231",
    #     "10.90.91.232",
    # ]
    #
    # run_upload_pipeline(MY_FILES, target_servers=ALL_SERVERS)

    TARGET_SERVERS = [
        "10.90.91.232",
    ]

    # 重启
    run_dist_task(restart_logic, target_servers=TARGET_SERVERS)
