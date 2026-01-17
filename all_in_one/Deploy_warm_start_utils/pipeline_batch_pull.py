import os
import json
import argparse
import posixpath
from rich.progress import track
from rich.console import Console
from fabric import Connection

# Import Configuration
# Removed MAIN_ROOT_PATH as it is undefined
from config import servers as SERVER_MANIFEST
from config import LOG_BUFFER_DIR
from sol_utils import routes_to_sol_string

console = Console()

# ================= SERVER FILTER =================
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


# =================================================

def fetch_remote_bks(conn, conf):
    """
    Executes a remote Python one-liner to extract BKS from all DBs.
    """
    # Fix: Construct remote path using the server-specific 'main_work_path'
    # path: .../all_in_one/SISR/log_buffer
    remote_log_dir = posixpath.join(conf['main_work_path'], LOG_BUFFER_DIR)

    remote_script = f"""
import os, sqlite3, json
base_dir = "{remote_log_dir}"
results = {{}}
if os.path.exists(base_dir):
    # Find folders starting with XL-
    instances = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d)) and d.startswith("XL-") and "XLTEST" not in d]
    for inst in instances:
        db_path = os.path.join(base_dir, inst, "shared.db")
        if not os.path.exists(db_path): continue
        try:
            conn = sqlite3.connect(f"file:{{db_path}}?mode=ro", uri=True)
            cur = conn.cursor()
            cur.execute("SELECT solution, score FROM global_best WHERE id=1")
            row = cur.fetchone()
            conn.close()
            if row:
                sol = json.loads(row[0])
                score = row[1]
                results[inst] = {{"solution": sol, "score": score}}
        except: pass
print(json.dumps(results))
"""
    remote_script_escaped = remote_script.replace('"', '\\"')

    try:
        result = conn.run(f"python3 -c \"{remote_script_escaped}\"", hide=True)
        return json.loads(result.stdout.strip())
    except Exception as e:
        console.print(f"[red]   Failed to fetch data: {e}[/red]")
        return {}


def main():
    parser = argparse.ArgumentParser(description="Batch Pull: Download BKS from servers and save as .sol")
    parser.add_argument("--save_dir", type=str, default="./pulled_solutions", help="Local directory to save .sol files")
    args = parser.parse_args()

    os.makedirs(args.save_dir, exist_ok=True)
    total_downloaded = 0

    # Filter servers
    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]No servers selected in 'to_run_servers'. Exiting.[/yellow]")
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

            # 1. Get data (pass entire conf dict)
            data_map = fetch_remote_bks(conn, conf)
            console.print(f"   Found {len(data_map)} instances")

            # 2. Save locally
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