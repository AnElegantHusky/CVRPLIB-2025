import os
import argparse
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from fabric import Connection

# Import configuration
from config import servers as SERVER_MANIFEST

console = Console()

# ================= Configuration Area =================

# 1. Default local Instances folder (for task allocation calculation)
# Must point to the original data folder you used to generate the task allocation
DEFAULT_LOCAL_INSTANCES_DIR = Path("./data/instances")  # Please modify based on actual situation

# 2. Remote target sub-directory name
REMOTE_SUB_DIR = "mahdi_outer_sol"

# 3. Filter servers to run (empty list means all)



# ================= Core Utility Functions =================

def get_sorted_sol_files(sol_dir_path):
    """
    Get all .sol files in the directory and sort them by filename.
    Returns: [(instance_name, file_path), ...]
    """
    path = Path(sol_dir_path)
    if not path.exists():
        raise FileNotFoundError(f"Sol directory not found: {path}")

    # Get all .sol files
    files = list(path.glob("*.sol"))

    # Sorting: This step is crucial. We must ensure the order matches the
    # order used when assigning tasks to servers.
    # We sort by instance_name (filename without extension).
    # Assuming filename format is "InstanceName.sol"
    sorted_files = sorted(files, key=lambda p: p.stem)

    # Return list of (name, path)
    return [(f.stem, f) for f in sorted_files]


def push_solutions_to_server(host_ip, files_to_upload, server_conf):
    """
    Handles upload logic for a single server.
    """
    user = server_conf['user']
    password = server_conf['password']
    port = server_conf.get('port', 22)
    base_path = Path(server_conf['main_work_path'])

    # Construct full remote path
    remote_dir = base_path / REMOTE_SUB_DIR

    if not files_to_upload:
        console.print(f"   No solutions in range for {host_ip}")
        return

    console.print(f"   🚀 Uploading {len(files_to_upload)} sols to {remote_dir}")

    try:
        # Establish connection
        with Connection(host=host_ip, user=user, port=port, connect_kwargs={"password": password}) as conn:

            # 1. Ensure remote directory exists
            conn.run(f"mkdir -p {remote_dir}", hide=True)

            # 2. Batch upload
            for _, local_path in track(files_to_upload, description=f"Pushing to {host_ip}...", transient=True):
                # Upload
                conn.put(str(local_path), str(remote_dir))

                # Modify permissions
                remote_file = remote_dir / local_path.name
                conn.run(f"chmod 666 {remote_file}", hide=True)

            console.print(f"   ✅ Done.")

    except Exception as e:
        console.print(f"   ❌ Upload failed: {e}")


# ================= Main Entry Point =================

if __name__ == "__main__":

    TO_RUN_SERVERS = [
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

    parser = argparse.ArgumentParser(description="Push local solutions based on sorted file index.")
    parser.add_argument("--sol_dir", required=True, type=str, help="Local directory containing the .sol files")

    args = parser.parse_args()
    sol_dir = Path(args.sol_dir)

    # 1. Read and sort all local solution files
    try:
        all_sols = get_sorted_sol_files(sol_dir)
        console.print(
            Panel(f"📂 Source: {sol_dir}\n📚 Total Files: {len(all_sols)} (Sorted)", title="Push Configuration"))
    except Exception as e:
        console.print(f"{e}")
        exit(1)

    # 2. Iterate through server configurations
    for srv in SERVER_MANIFEST:
        host_ip = srv['host']

        # Filter
        if TO_RUN_SERVERS and host_ip not in TO_RUN_SERVERS:
            continue

        console.print(f"\n🔗 Node: {host_ip}")

        # 3. Get Range
        idx_range = srv.get('instance_range')
        if not idx_range:
            console.print(f"   [red]❌ Skipped: No 'instance_range' defined[/red]")
            continue

        start_idx, end_idx = idx_range

        # 4. Slicing logic (Slice directly on the sorted sol file list)
        # Note: This assumes the count and order of files in the local sol folder strictly
        # correspond to the instance list used during assignment.
        # If sol files are fewer than instances (e.g., some didn't finish), this slicing might be "misaligned".
        # But since you requested splitting by index, we execute this logic strictly.

        if start_idx >= len(all_sols):
            console.print(
                f"   [yellow]⚠️ Range {idx_range} is out of bounds (Total Sols: {len(all_sols)}). Skipping.[/yellow]")
            continue

        # Extract files responsible for this server
        target_sols = all_sols[start_idx: min(end_idx, len(all_sols))]

        console.print(f"   🎯 Range: {start_idx}-{end_idx} (Selected: {len(target_sols)} files)")

        # 5. Push
        push_solutions_to_server(host_ip, target_sols, srv)

    console.print("\n✨ Batch Push Completed.")