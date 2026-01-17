import posixpath
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

top_A_name = "Competition_Deploy_Hybird"
top_B_name = "Warm_Start_Deploy_Hybrid"

class ServerNode:
    def __init__(self, config):
        self.host = config['host']
        self.user = config['user']
        self.port = config.get('port', 22)
        self.password = config['password']

        # 1. 基础路径 (宿主机项目总根目录)
        self.base_dir = config['base_path'].rstrip('/')
        self.instance_range = config.get('instance_range', (0, 0))

        # [源路径 A]
        # 结果示例: /home/ei/.../Competition_Deploy_Hybird/all_in_one/SISR
        self.path_A_work = posixpath.join(self.base_dir, MAIN_ROOT_PATH.rstrip('/'))
        # 结果示例: /home/ei/.../Competition_Deploy_Hybird/all_in_one
        self.path_A_root = posixpath.dirname(self.path_A_work)

        # [目标路径 B]
        self.path_B_work = posixpath.join(self.base_dir, WARM_START_ROOT_PATH.rstrip('/'))
        self.path_B_root = posixpath.dirname(self.path_B_work)

        # path_A_top: .../Competition_Deploy_Hybird
        self.path_A_top = posixpath.join(self.base_dir, top_A_name)

        # path_B_top: .../Warm_Start_Deploy_Hybrid
        self.path_B_top = posixpath.join(self.base_dir, top_B_name)

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
        全量克隆：将 Competition_Deploy_Hybird 整个目录 -> 复制到 Warm_Start_Deploy_Hybrid
        """
        console.print(f"[cyan]📦 {self.host}: 同步整个项目目录 (A -> B)...[/cyan]")

        # 1. 确保 B 的顶层目录存在
        self.run_cmd(f"mkdir -p {self.path_B_top}", work_dir="/tmp")

        # 2. rsync 同步
        # 源: path_A_top/ (Competition_Deploy_Hybird 下的所有内容)
        # 目标: path_B_top/ (Warm_Start_Deploy_Hybrid)
        # 排除路径需要调整，因为现在根目录变了
        # log_buffer 现在相对于根目录的路径是 all_in_one/SISR/log_buffer
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