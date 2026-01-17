import os
from fabric import Connection
from invoke.exceptions import UnexpectedExit
from rich.console import Console

console = Console()

# 引入 Config 中的路径常量
# 确保 config.py 与此文件在同一目录下，或者在 PYTHONPATH 中
try:
    from config import MAIN_ROOT_PATH, WARM_START_ROOT_PATH
except ImportError:
    # 默认回退值，防止报错
    MAIN_ROOT_PATH = "Competition_Deploy_Hybird/all_in_one/SISR/"
    WARM_START_ROOT_PATH = "Warm_Start_Deploy_Hybrid/all_in_one/SISR/"


class ServerNode:
    def __init__(self, config):
        self.host = config['host']
        self.user = config['user']
        self.port = config.get('port', 22)
        self.password = config['password']

        # 1. 基础路径 (宿主机项目总根目录)
        self.base_dir = config['base_path'].rstrip('/')
        self.instance_range = config.get('instance_range', (0, 0))

        # 2. 计算 A (Master) 的路径
        # path_A_work: .../all_in_one/SISR (代码运行位置)
        # path_A_root: .../all_in_one (挂载到容器 /app 的位置，包含 AILS2, FILO2)
        self.path_A_work = os.path.join(self.base_dir, MAIN_ROOT_PATH.rstrip('/'))
        self.path_A_root = os.path.dirname(self.path_A_work)

        # 3. 计算 B (Explorer) 的路径
        self.path_B_work = os.path.join(self.base_dir, WARM_START_ROOT_PATH.rstrip('/'))
        self.path_B_root = os.path.dirname(self.path_B_work)

        # B 的父级目录，用于 mkdir
        self.path_B_parent = os.path.dirname(self.path_B_root)

        self.conn = None

    def connect(self):
        """建立 SSH 连接"""
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

    def run_cmd(self, cmd, work_dir=None, background=False, warn=True):
        """
        通用命令执行
        :param work_dir: 执行命令的目录，默认为 base_dir
        :param background: 是否后台运行 (nohup)
        """
        target_dir = work_dir if work_dir else self.base_dir

        # 构造组合命令
        full_cmd = f"cd {target_dir} && {cmd}"

        if background:
            full_cmd = f"nohup {full_cmd} > /dev/null 2>&1 &"

        try:
            # hide=True 隐藏默认输出，我们手动打印
            result = self.conn.run(full_cmd, hide=True, warn=warn)

            if result.failed:
                console.print(
                    f"[bold red]⚠️  CMD Error on {self.host}:[/bold red]\nCommand: {full_cmd}\nError: {result.stderr}")
                return False, result.stderr.strip()

            return True, result.stdout.strip()

        except UnexpectedExit as e:
            console.print(f"[bold red]❌ Critical Error on {self.host}:[/bold red] {e}")
            return False, str(e)

    def check_docker_status(self):
        """检查 Docker 是否存活"""
        ok, _ = self.run_cmd("docker info", work_dir="/tmp", warn=True)
        return ok

    def sync_artifacts(self):
        """
        [核心功能] 宿主机内部全量克隆：
        将 A 的 all_in_one 整个复制到 B，排除 log_buffer
        """
        console.print(f"[cyan]📦 {self.host}: 正在同步 all_in_one (Source -> Target)...[/cyan]")

        # 1. 确保目标父目录存在 (例如 .../Warm_Start_Deploy_Hybrid/)
        self.run_cmd(f"mkdir -p {self.path_B_parent}", work_dir="/tmp")

        # 2. 使用 rsync 进行全量同步
        # --delete: 确保 B 和 A 一致 (可选，暂不加防止误删)
        # --exclude: 排除数据文件夹和缓存
        # {self.path_A_root}/ 注意末尾斜杠，表示复制目录下的内容
        cmd_sync = (
            f"rsync -av "
            f"--exclude 'SISR/log_buffer' "  # 排除数据
            f"--exclude '__pycache__' "
            f"--exclude '*.git' "
            f"{self.path_A_root}/ {self.path_B_root}/"
        )

        ok, err = self.run_cmd(cmd_sync, work_dir="/tmp")

        if ok:
            console.print(f"   ✅ {self.host}: 同步完成")
            return True
        else:
            # 如果 rsync 失败 (极少见)，尝试用 cp 回退方案
            console.print(f"   ⚠️ {self.host}: rsync 失败，尝试 cp...")
            cmd_cp = (
                f"rm -rf {self.path_B_root} && "
                f"cp -r {self.path_A_root} {self.path_B_root} && "
                f"rm -rf {self.path_B_work}/log_buffer"  # 删掉复制过去的数据
            )
            ok_cp, err_cp = self.run_cmd(cmd_cp, work_dir="/tmp")
            if ok_cp:
                console.print(f"   ✅ {self.host}: cp 同步完成")
                return True
            else:
                console.print(f"   ❌ {self.host}: 同步彻底失败 - {err_cp}")
                return False