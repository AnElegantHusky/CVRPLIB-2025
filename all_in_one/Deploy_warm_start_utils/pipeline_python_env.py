import sys
import time
from rich.console import Console
from rich.table import Table
from fabric import Connection
from invoke.exceptions import UnexpectedExit

# Import Configuration
from config import servers as SERVER_MANIFEST

console = Console()

# ================= SERVER FILTER =================
# Define the IPs of the servers where you want to setup the environment
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

# List of packages required for Guardian/Monitoring scripts
# Note: sqlite3 is usually built-in, but pandas/rich are not.
REQUIRED_PACKAGES = [
    "pandas",
]


def check_and_install(node_conf):
    host = node_conf['host']
    user = node_conf['user']
    password = node_conf['password']
    port = node_conf.get('port', 22)

    console.print(f"\n[bold blue]🔗 Connecting to: {host}[/bold blue]")

    try:
        conn = Connection(
            host=host,
            user=user,
            port=port,
            connect_kwargs={"password": password},
            connect_timeout=5
        )

        # 1. Check Python Version
        console.print("   🔍 Checking Python version...")
        res = conn.run("python3 --version", hide=True, warn=True)
        if res.failed:
            console.print(f"[red]   ❌ Python3 not found on {host}![/red]")
            return False, "No Python3"
        console.print(f"   ✅ {res.stdout.strip()}")

        # 2. Check SQLite3 availability (Native)
        # Many minimal Linux installs have python but lack the sqlite3.so binding
        console.print("   🔍 Checking native sqlite3 support...")
        res_sql = conn.run("python3 -c 'import sqlite3; print(sqlite3.version)'", hide=True, warn=True)

        sqlite_status = "OK"
        if res_sql.failed:
            console.print("[yellow]   ⚠️  Native sqlite3 module missing. Trying to fix via pip...[/yellow]")
            REQUIRED_PACKAGES.append("pysqlite3-binary")  # Try to install binary wheel if system lib is missing
            sqlite_status = "Patched"
        else:
            console.print(f"   ✅ SQLite3 Version: {res_sql.stdout.strip()}")

        # 3. Install PIP Packages
        pkgs_str = " ".join(REQUIRED_PACKAGES)
        console.print(f"   📦 Installing packages: [cyan]{pkgs_str}[/cyan]...")

        # We use --user to avoid permission issues without sudo
        # We use -i https://pypi.tuna.tsinghua.edu.cn/simple for speed in China (optional)
        install_cmd = f"python3 -m pip install --user --upgrade {pkgs_str} -i https://mirrors.tools.huawei.com/pypi/simple"

        res_install = conn.run(install_cmd, hide=True, warn=True)

        if res_install.failed:
            console.print(f"[red]   ❌ Install failed: {res_install.stderr.strip()}[/red]")
            return False, "Install Error"

        console.print("   ✅ Installation successful.")

        conn.close()
        return True, f"Success ({sqlite_status})"

    except Exception as e:
        console.print(f"[red]   ❌ Connection Error: {e}[/red]")
        return False, str(e)


def main():
    # Filter servers
    active_nodes = [s for s in SERVER_MANIFEST if s['host'] in to_run_servers]

    if not active_nodes:
        console.print("[yellow]No servers selected in 'to_run_servers'. Exiting.[/yellow]")
        return

    results = []

    for node in active_nodes:
        success, msg = check_and_install(node)
        results.append({
            "host": node['host'],
            "status": "✅" if success else "❌",
            "msg": msg
        })

    # Summary Table
    console.print("\n")
    table = Table(title="Environment Setup Summary")
    table.add_column("Host", style="cyan")
    table.add_column("Status", justify="center")
    table.add_column("Message")

    for r in results:
        table.add_row(r["host"], r["status"], r["msg"])

    console.print(table)


if __name__ == "__main__":
    main()