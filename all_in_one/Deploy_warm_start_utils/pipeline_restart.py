import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel

# 1. 引入驱动器
from conn_utils import run_dist_task

# 2. 引入配置 (用于获取 instance_range)
from config import servers as SERVER_MANIFEST

# 3. 引入工具库
from pipeline_docker_cvrplib_cmd import exec_in_cvrplib, CONTAINER_NAME as CVRP_NAME
from pipeline_docker_warmstart_cmd import exec_in_warmstart, CONTAINER_NAME as WS_NAME
from pipeline_upload_files import run_upload_pipeline

console = Console()

# === 配置 ===
# 1. 本地 Instances 路径 (用于获取文件名列表)
# 假设脚本在 pipeline 目录下，数据在 ../data/instances
LOCAL_INSTANCES_DIR = Path(__file__).resolve().parent.parent / "SISR" / "data" / "instances"
print(LOCAL_INSTANCES_DIR)

# 2. 远程配置
REMOTE_INSTANCE_FOLDER = "instances"  # 容器内的文件夹名
RESTART_SCRIPT = "main_for_all_restart.py"



# === 预处理：全局文件列表 ===
# 这一步在跳板机本地执行，确保顺序绝对一致
try:
    if not LOCAL_INSTANCES_DIR.exists():
        console.print(f"[bold red]❌ Error: Local instance dir not found: {LOCAL_INSTANCES_DIR}[/bold red]")
        sys.exit(1)

    ALL_FILES = sorted(list(LOCAL_INSTANCES_DIR.glob("*.vrp")))
    console.print(f"[green]✅ Loaded {len(ALL_FILES)} instances locally from {LOCAL_INSTANCES_DIR}[/green]")
except Exception as e:
    console.print(f"[bold red]❌ Error loading local files: {e}[/bold red]")
    sys.exit(1)


# === 辅助函数 ===
def ensure_container_alive(conn, container_name):
    """(保持不变) 确保容器存活"""
    check_cmd = f"docker inspect -f '{{{{.State.Running}}}}' {container_name}"
    res = conn.run(check_cmd, warn=True, hide=True)
    if res.ok and res.stdout.strip().lower() == 'true':
        console.print(f"      ✅ [Check] {container_name} is running")
        return True
    else:
        console.print(f"      ⚠️ [Check] {container_name} is STOPPED. Starting...")
        conn.run(f"docker start {container_name}", warn=True, hide=True)
        return True


def prepare_server_env(conn, host_ip):
    """
    Phase 1: 串行执行环境准备
    1. 上传最新的 restart_clean.py
    2. 运行它
    """
    console.print(f"   🧹 [Clean] Preparing Environment on {host_ip}...", style="yellow")

    # 同时清理之前的 restart logs
    run_cmd = f"rm -f *_restart.log && python3 restart_clean.py"
    exec_in_cvrplib(conn, run_cmd, background=False)

    console.print(f"      ✅ Cleanup & Extraction Finished.")
    return True

def trigger_explicit_restart(conn, host_ip):
    """
    本地切片 -> 构建显式命令 -> 远程执行
    """
    # 1. 获取范围配置
    server_conf = next((s for s in SERVER_MANIFEST if s['host'] == host_ip), None)
    if not server_conf or 'instance_range' not in server_conf:
        console.print(f"      ❌ [Config] No instance_range found for {host_ip}, skipping.")
        return

    # 2. 本地切片 (Python Slice)
    start_idx, end_idx = server_conf['instance_range']
    target_files = ALL_FILES[start_idx:end_idx]

    if not target_files:
        console.print(f"      ⚠️  Range [{start_idx}:{end_idx}] is empty or out of bounds.")
        return

    console.print(f"   🚀 Starting {len(target_files)} instances (Range: {start_idx}-{end_idx})")

    # 打印前3个和最后1个名字，用于检查
    preview_names = [f.stem for f in target_files]
    preview_str = ", ".join(preview_names[:3]) + ("..." if len(preview_names) > 3 else "") + (
        preview_names[-1] if len(preview_names) > 3 else "")
    console.print(f"      [dim]Targets: {preview_str}[/dim]")

    # 3. 构建显式命令串
    # 我们把所有 nohup 命令用 '&' 连接，最好包裹在 () 里或者直接串行发送
    # 为了保险起见，我们构造一个长的单行命令，用 ; 或 & 连接
    # 形式: nohup python ... & nohup python ... &

    cmd_list = []
    for file_path in target_files:
        instance_name = file_path.stem
        # 构造单条命令
        cmd = (
            f"nohup python3 -u {RESTART_SCRIPT} "
            f"{REMOTE_INSTANCE_FOLDER} \"{instance_name}\" "
            f"> \"{instance_name}_restart.log\" 2>&1 &"
        )
        cmd_list.append(cmd)
        exec_in_cvrplib(conn, cmd, background=True)
        print(cmd)

    # === 关键修改 ===
    # 1. 用括号 ( ) 将所有命令包起来，形成一个 Subshell
    # 2. 这样 exec_in_cvrplib 自动添加的 cd dir && ( ... ) 就会对括号内所有命令生效
    full_batch_cmd = "(" + " ".join(cmd_list) + " echo 'Batch Triggered' )"

    # 4. 执行
    # background=True 会让 docker exec -d ... 在后台执行这个括号里的所有内容


    # cmd_list = []
    # for file_path in target_files:
    #     instance_name = file_path.stem  # 去掉 .vrp
    #     # 构造单条命令
    #     # 注意：日志名必须区分开
    #     cmd = (
    #         f"nohup python3 -u {RESTART_SCRIPT} "
    #         f"{REMOTE_INSTANCE_FOLDER} \"{instance_name}\" "
    #         f"> \"{instance_name}_restart.log\" 2>&1 &"
    #     )
    #     cmd_list.append(cmd)
    #     print(cmd)
    #
    # # 将所有后台命令拼接，最后加个 echo
    # # 形式: cmd1 & cmd2 & echo "Done"
    # full_batch_cmd = " ".join(cmd_list) + " echo 'Batch Triggered'"
    #
    # # 4. 执行 (background=True 意味着整个串在 docker exec -d 中执行)
    # exec_in_cvrplib(conn, full_batch_cmd, background=True)


# === 核心业务逻辑 ===
def my_restart_logic(conn, host_ip):
    console.print(Panel(f"Executing Restart Sequence on {host_ip}", style="cyan"))

    # Step 1: 检查基础设施
    if not (ensure_container_alive(conn, CVRP_NAME) and ensure_container_alive(conn, WS_NAME)):
        return

    # Step 2: 清理重启环境
    prepare_server_env(conn, host_ip)

    # Step 3: 显式启动任务
    trigger_explicit_restart(conn, host_ip)


# === 入口 ===
if __name__ == "__main__":
    # 格式: (本地文件路径, 目标标记: "main" | "warm_start" | "both")
    MY_FILES = [
        # ("./files_to_upload/extract_survivor_history.py", "both"),
        # ("./files_to_upload/guardian.py", "warm_start"),
        # ("./files_to_upload/main_for_all_warm_start.py", "warm_start"),
        # ("./files_to_upload/service_ingest_sol.py", "main"),
        # ("./files_to_upload/write_outer_sol.py", "both"),
        ("./files_to_upload/main_for_all_restart.py", "main"),
        ("./files_to_upload/restart_clean.py", "main"),
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

    run_dist_task(my_restart_logic, target_servers=TARGET_SERVERS)
