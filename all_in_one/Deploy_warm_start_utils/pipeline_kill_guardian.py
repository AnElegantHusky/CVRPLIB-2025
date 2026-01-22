import sys
from rich.console import Console
from rich.panel import Panel

# 引入你的基础库
from conn_utils import run_dist_task
from config import servers as SERVER_MANIFEST

console = Console()

# === 配置 ===
TARGET_CONTAINER = "warm_start"


def kill_process_logic(conn, host_ip):
    console.print(Panel(f"🔪 Killing processes in [bold]{TARGET_CONTAINER}[/bold] on {host_ip}", style="red"))

    # 1. 检查容器是否存活
    check_cmd = f"docker inspect -f '{{{{.State.Running}}}}' {TARGET_CONTAINER}"
    res = conn.run(check_cmd, warn=True, hide=True)

    if not res.ok or res.stdout.strip().lower() != 'true':
        console.print(f"   ⚠️ Container {TARGET_CONTAINER} is not running. Skipping.")
        return

    # 2. 构造组合杀戮命令
    # 逻辑：
    # - pkill -9 -f "pattern": 强制匹配命令行参数查杀
    # - || true: 即使没找到进程也不报错，保证后续命令继续执行
    # - 顺序：先杀 Guardian (防止重启别人) -> 再杀 Python wrapper -> 最后杀 Java

    kill_cmds = [
        "echo 'Step 1: Killing Guardian (The Supervisor)...'",
        "pkill -9 -f 'guardian.py' || true",
        "sleep 1",  # 给一点喘息时间

        "echo 'Step 2: Killing Workers (main_for_all)...'",
        "pkill -9 -f 'main_for_all' || true",

        "echo 'Step 3: Killing Solvers (Java)...'",
        "pkill -9 -f 'java' || true",

        "echo 'Step 4: Cleanup Leftover Python...'",
        # 注意：这里要小心，别杀错了系统进程，但容器里通常只有业务python
        # 如果只想杀特定脚本，上面已经涵盖了。这一步作为保险，杀所有关联 python
        # "pkill -9 -f 'python' || true" # 慎用，除非容器专用于此
    ]

    full_kill_cmd = " && ".join(kill_cmds)

    # 在容器内执行
    # 使用 /bin/bash -c 确保 && 逻辑在容器内被 Shell 解析
    docker_exec_cmd = f"docker exec {TARGET_CONTAINER} /bin/bash -c \"{full_kill_cmd}\""

    console.print(f"   🔥 Executing Kill Sequence...")
    conn.run(docker_exec_cmd, warn=True, hide=False)

    # 3. 验证结果 (Verify)
    console.print(f"   🔍 Verifying cleanup...")
    verify_cmd = (
        f"docker exec {TARGET_CONTAINER} ps aux | "
        f"grep -E 'guardian|main_for_all|java' | grep -v grep"
    )

    verify_res = conn.run(verify_cmd, warn=True, hide=True)

    if verify_res.stdout.strip():
        console.print(f"[bold red]   ❌ Warning: Some processes are still alive![/bold red]")
        console.print(f"[dim]{verify_res.stdout.strip()}[/dim]")

        # 可选：如果还有残留，启用核打击（重启容器）
        # console.print(f"   ☢️ Trying Nuclear Option: Restarting Container...")
        # conn.run(f"docker restart {TARGET_CONTAINER}")
    else:
        console.print(f"   ✅ [bold green]All targets eliminated. Clean slate.[/bold green]")


if __name__ == "__main__":
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