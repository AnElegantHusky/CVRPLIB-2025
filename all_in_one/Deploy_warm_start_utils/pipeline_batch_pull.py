import os
import json
import argparse
from rich.progress import track
from rich.console import Console
from fabric import Connection

# 引入配置
from config import servers as SERVER_MANIFEST
from sol_utils import routes_to_sol_string

console = Console()

# ================= 配置区域 =================
# 1. 筛选要拉取的服务器
to_run_servers = [
    "10.90.91.100",
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
    # "10.90.91.232",
]

# 2. 容器名称
# 也就是你运行 docker ps 看到的 NAMES 列
# 如果不确定，可以写一个列表尝试，或者统一叫 cvrplib
CONTAINER_NAME = "cvrplib"


# ===========================================

def fetch_remote_bks_adaptive(conn):
    """
    自适应拉取：不依赖 Config 路径，而是让容器内的 Python 自己找 log_buffer 在哪
    """

    # 这段 Python 代码会在容器内部执行
    # 它包含了路径探测逻辑
    remote_script = """
import os
import sqlite3
import json

# 1. 定义候选路径 (根据你描述的三种挂载情况)
candidates = [
    "/app/log_buffer",                       # Case 1: 挂载的是 SISR
    "/app/SISR/log_buffer",                  # Case 2: 挂载的是 all_in_one
    "/app/all_in_one/SISR/log_buffer",       # Case 3: 挂载的是 Competition_Root
    "log_buffer",                            # 相对路径备用
    "SISR/log_buffer",
    "all_in_one/SISR/log_buffer",
    "Competition_Deploy_Hybird/all_in_one/SISR/log_buffer",
]

target_dir = None

# 2. 寻找真正的 log_buffer
for path in candidates:
    if os.path.exists(path) and os.path.isdir(path):
        # 简单验证：里面是否有 XL- 开头的文件夹
        try:
            subdirs = os.listdir(path)
            if any(d.startswith("XL-") for d in subdirs):
                target_dir = path
                break
        except:
            continue

results = {}

if target_dir:
    # 3. 找到路径后，开始遍历读取
    # results["_debug_path"] = target_dir # 调试用：看看到底找到了哪个路径

    instances = [d for d in os.listdir(target_dir) if d.startswith("XL-") and "XLTEST" not in d]

    for inst in instances:
        db_path = os.path.join(target_dir, inst, "shared.db")
        if not os.path.exists(db_path): continue

        try:
            # 必须用只读模式，防止锁死
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT solution, score FROM global_best WHERE id=1")
            row = cur.fetchone()
            conn.close()

            if row:
                sol = json.loads(row[0])
                score = row[1]
                results[inst] = {"solution": sol, "score": score}
        except:
            pass

print(json.dumps(results))
"""
    # 命令行转义处理
    remote_script_escaped = remote_script.replace('"', '\\"')

    # 核心命令：docker exec inside container
    cmd = f"docker exec -i {CONTAINER_NAME} python3 -c \"{remote_script_escaped}\""

    try:
        result = conn.run(cmd, hide=True, warn=True)
        if result.failed:
            # 如果失败，可能是容器名字不对，或者容器里没 python3
            console.print(f"[red]   Docker exec failed: {result.stderr.strip()}[/red]")
            return {}

        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        console.print(f"[red]   JSON Parse Error. Output: {result.stdout.strip()[:50]}...[/red]")
        return {}
    except Exception as e:
        console.print(f"[red]   Unknown Error: {e}[/red]")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Batch Pull: Adaptive path discovery inside Docker")
    parser.add_argument("--save_dir", type=str, default="./pulled_solutions", help="Local directory to save .sol files")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    total_downloaded = 0

    # 筛选服务器
    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]No servers selected in 'to_run_servers'.[/yellow]")
        return

    for conf in active_nodes:
        host = conf['host']
        console.print(f"\n[bold blue]🔗 Connecting to: {host}[/bold blue]")

        try:
            conn = Connection(
                host=host,
                user=conf['user'],
                port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']},
                connect_timeout=5
            )

            # === 调用自适应拉取函数 ===
            data_map = fetch_remote_bks_adaptive(conn)

            # debug_path = data_map.pop("_debug_path", "Unknown")
            # console.print(f"   📂 Found log_buffer at: [dim]{debug_path}[/dim]")
            console.print(f"   Found {len(data_map)} instances")

            # 保存文件 (无需修改)
            for inst_name, data in data_map.items():
                routes = data['solution']
                score = data['score']
                sol_content = routes_to_sol_string(routes, score, inst_name)

                file_path = os.path.join(args.save_dir, f"{inst_name}.sol")
                with open(file_path, "w", encoding='utf-8') as f:
                    f.write(sol_content)

            total_downloaded += len(data_map)
            conn.close()

        except Exception as e:
            console.print(f"[red]   Connection error: {e}[/red]")
            continue

    console.rule("[green]Pull Completed[/green]")
    console.print(f"Total .sol files saved: {total_downloaded}")


if __name__ == "__main__":
    main()