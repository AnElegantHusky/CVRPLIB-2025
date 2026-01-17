import os
import json
import argparse
import posixpath
from rich.console import Console
from rich.progress import track
from fabric import Connection

# Import Configuration
# Removed MAIN_ROOT_PATH
from config import servers as SERVER_MANIFEST
from config import LOG_BUFFER_DIR
from sol_utils import parse_sol_file

console = Console()

# ================= SERVER FILTER =================
to_run_servers = [
    "10.90.91.100",
    # "10.90.91.101",
    "10.90.91.124",
]


# =================================================

def build_instance_map(nodes):
    """
    Scans servers to determine which server holds which Instance ID.
    Returns: dict { "XL-Instance-Name": server_config_dict }
    """
    mapping = {}
    console.print("[yellow]Scanning servers for instance distribution...[/yellow]")

    for conf in nodes:
        host = conf['host']
        try:
            conn = Connection(
                host=host, user=conf['user'], port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']}, connect_timeout=3
            )

            # Fix: Use main_work_path from config dict
            remote_log_dir = posixpath.join(conf['main_work_path'], LOG_BUFFER_DIR)

            result = conn.run(f"ls -1 {remote_log_dir}", hide=True, warn=True)

            if result.ok:
                folders = result.stdout.strip().split('\n')
                count = 0
                for f in folders:
                    f = f.strip()
                    if f.startswith("XL-") and "XLTEST" not in f:
                        mapping[f] = conf
                        count += 1
                console.print(f"   {host}: Hosts {count} instances")

            conn.close()
        except Exception as e:
            console.print(f"[red]   {host} Scan failed: {e}[/red]")

    return mapping


def main():
    parser = argparse.ArgumentParser(description="Batch Push: Inject local .sol files into remote DBs")
    parser.add_argument("--sol_dir", type=str, required=True, help="Path to local directory containing .sol files")
    args = parser.parse_args()

    if not os.path.exists(args.sol_dir):
        console.print("[red]Error: Local directory does not exist.[/red]")
        return

    # 1. Parse local .sol files
    local_sols = {}
    files = [f for f in os.listdir(args.sol_dir) if f.endswith(".sol")]

    console.print(f"Parsing {len(files)} local .sol files...")
    for fname in files:
        inst_name = os.path.splitext(fname)[0]
        if not inst_name.startswith("XL-"):
            continue

        path = os.path.join(args.sol_dir, fname)
        score, routes = parse_sol_file(path)

        if routes:
            local_sols[inst_name] = (score, json.dumps(routes))

    console.print(f"Parsed {len(local_sols)} valid solutions.")

    # 2. Filter servers
    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]
    if not active_nodes:
        console.print("[yellow]No servers selected in 'to_run_servers'. Exiting.[/yellow]")
        return

    # 3. Build Map
    srv_map = build_instance_map(active_nodes)

    # 4. Group tasks
    tasks_per_server = {}
    for inst_name, (score, sol_json) in local_sols.items():
        if inst_name in srv_map:
            conf = srv_map[inst_name]
            host = conf['host']
            if host not in tasks_per_server:
                tasks_per_server[host] = []
            tasks_per_server[host].append((inst_name, score, sol_json))

    # 5. Execute Injection
    injector_local_path = "server_db_injector.py"
    if not os.path.exists(injector_local_path):
        console.print(f"[red]Error: {injector_local_path} not found.[/red]")
        return

    for host, tasks in tasks_per_server.items():
        console.rule(f"Processing Server: {host} ({len(tasks)} solutions)")

        conf = next(c for c in SERVER_MANIFEST if c['host'] == host)

        try:
            conn = Connection(
                host=host, user=conf['user'], port=conf.get('port', 22),
                connect_kwargs={"password": conf['password']}
            )

            conn.put(injector_local_path, remote="/tmp/server_db_injector.py")

            success_cnt = 0

            for inst_name, score, sol_json in track(tasks, description=f"Injecting to {host}..."):
                # Fix: Use main_work_path from config dict
                remote_db_path = posixpath.join(
                    conf['main_work_path'], LOG_BUFFER_DIR, inst_name, "shared.db"
                )

                safe_json = sol_json.replace('"', '\\"')
                cmd = f"python3 /tmp/server_db_injector.py \"{remote_db_path}\" {score} \"{safe_json}\""

                res = conn.run(cmd, hide=True, warn=True)

                if "SUCCESS" in res.stdout:
                    success_cnt += 1

            console.print(f"   ✅ Successfully injected/updated: {success_cnt}/{len(tasks)}")
            conn.close()

        except Exception as e:
            console.print(f"[red]   Error on {host}: {e}[/red]")


if __name__ == "__main__":
    main()