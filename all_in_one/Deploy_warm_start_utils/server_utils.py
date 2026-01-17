import posixpath
from fabric import Connection
from invoke.exceptions import UnexpectedExit
from rich.console import Console

console = Console()


class ServerNode:
    def __init__(self, config):
        self.host = config['host']
        self.user = config['user']
        self.port = config.get('port', 22)
        self.password = config['password']

        # 基础路径 (仅作备用，主要逻辑使用 work_path)
        self.base_dir = config['base_path'].rstrip('/')
        self.instance_range = config.get('instance_range', (0, 0))

        # ==========================================================
        # 路径逻辑重构：基于 Config 中的全路径反向解析
        # ==========================================================

        # [源路径 A] (Master)
        # Config: .../Competition_Deploy_Hybird/all_in_one/SISR/
        self.path_A_work = config['main_work_path'].rstrip('/')

        # 倒推上一级: .../Competition_Deploy_Hybird/all_in_one
        self.path_A_root = posixpath.dirname(self.path_A_work)

        # 倒推顶层: .../Competition_Deploy_Hybird (这是我们要复制的根目录)
        self.path_A_top = posixpath.dirname(self.path_A_root)

        # [目标路径 B] (Warm Start)
        # Config: .../Warm_Start_Deploy_Hybrid/all_in_one/SISR/
        self.path_B_work = config['warm_start_work_path'].rstrip('/')
        self.path_B_root = posixpath.dirname(self.path_B_work)
        self.path_B_top = posixpath.dirname(self.path_B_root)

        self.conn = None

    def connect(self):
        try:
            self.conn = Connection(
                host=self.host,
                user=self.user,
                port=self.port,
                connect_kwargs={"password": self.password},
                connect_timeout=10
            )
            return True
        except Exception as e:
            console.print(f"[bold red]❌ {self.host} 连接失败: {e}[/bold red]")
            return False

    def run_cmd(self, cmd, work_dir=None, background=False):
        # 默认在 base_dir 执行，但强烈建议传入 work_dir
        target_dir = work_dir if work_dir else self.base_dir

        full_cmd = f"cd {target_dir} && {cmd}"
        if background:
            full_cmd = f"nohup {full_cmd} > /dev/null 2>&1 &"

        try:
            result = self.conn.run(full_cmd, hide=True, warn=True)
            if result.failed:
                console.print(f"[red]⚠️ {self.host} Error:[/red] {result.stderr.strip()}")
                return False, result.stderr.strip()
            return True, result.stdout.strip()
        except UnexpectedExit as e:
            return False, str(e)

    def sync_artifacts(self):
        """
        全量克隆：将 Path_A_Top 整个目录 -> 复制到 Path_B_Top
        例如: Competition_Deploy_Hybird -> Warm_Start_Deploy_Hybrid
        """
        console.print(f"[cyan]📦 {self.host}: 同步项目目录 (A -> B)...[/cyan]")
        console.print(f"   Source: {self.path_A_top}")
        console.print(f"   Target: {self.path_B_top}")

        # 1. 确保 B 的父级目录存在
        # 我们取 path_B_top 的父级目录作为 mkdir 的目标
        path_B_parent = posixpath.dirname(self.path_B_top)
        self.run_cmd(f"mkdir -p {path_B_parent}", work_dir="/tmp")

        # 2. rsync 同步
        # 源: path_A_top/ (注意末尾斜杠，代表复制内容)
        # 目标: path_B_top/ (会自动创建同名目录或放入其中，这里我们希望内容对拷)
        # 我们先 mkdir 目标目录
        self.run_cmd(f"mkdir -p {self.path_B_top}", work_dir="/tmp")

        cmd = (
            f"rsync -az "
            f"--exclude 'all_in_one/SISR/log_buffer' "
            f"--exclude '__pycache__' "
            f"--exclude '*.git' "
            f"{self.path_A_top}/ {self.path_B_top}/"
        )

        ok, err = self.run_cmd(cmd, work_dir="/tmp")
        if ok:
            console.print(f"   ✅ 同步完成")
        else:
            console.print(f"   ❌ 同步失败: {err}")
        return ok