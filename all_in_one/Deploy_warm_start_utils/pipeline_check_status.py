import time
from datetime import datetime
from fabric import Connection

# ================= 配置区域 =================
PROCESS_KEYWORD = "main_for_all_final.py"
FETCH_INTERVAL = 60  # 检查间隔 (秒)，默认设为 60 秒检查一次，可自行修改

# 团队服务器列表 (保持原样)
SERVERS = [
    {"host": "10.90.91.100", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.101", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.124", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.125", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.126", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.127", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.163", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.167", "user": "ei", "password": "ei@noah2012", "port": 22},
    {"host": "10.90.91.49", "user": "cvrp", "password": "123456", "port": 22},
    {"host": "10.90.91.51", "user": "cvrp", "password": "123456", "port": 22},
    {"host": "10.90.91.231", "user": "cvrp", "password": "123456", "port": 22},
    {"host": "10.90.91.232", "user": "cvrp", "password": "123456", "port": 22},
]


# ================= 核心逻辑 =================

def log_with_time(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def check_servers():
    log_with_time(f"🚀 开始新一轮服务器进程检查...")

    active_servers = 0
    total_processes = 0
    error_servers = 0

    for srv in SERVERS:
        try:
            # 建立 SSH 连接
            with Connection(host=srv['host'], user=srv['user'], port=srv['port'],
                            connect_kwargs={"password": srv['password']},
                            connect_timeout=5) as conn:

                # 执行 grep 命令统计进程数
                cmd = f"ps -ef | grep '{PROCESS_KEYWORD}' | grep -v grep | wc -l"
                result = conn.run(cmd, hide=True, warn=True)

                if result.ok:
                    count = int(result.stdout.strip())
                    if count > 0:
                        log_with_time(f"✅ {srv['host']} : 运行中 ({count} 个进程)")
                        active_servers += 1
                        total_processes += count
                    else:
                        log_with_time(f"❌ {srv['host']} : 未发现进程 (DOWN)")
                else:
                    log_with_time(f"⚠️ {srv['host']} : 命令执行失败")
                    error_servers += 1

        except Exception as e:
            log_with_time(f"⚠️ {srv['host']} : 连接异常 ({str(e)})")
            error_servers += 1

    print("-" * 50)
    log_with_time(f"📊 汇总: 在线服务器 {active_servers}/{len(SERVERS)} | 总进程数: {total_processes}")
    print("=" * 50)


def main():
    log_with_time(f"🛡️ 监控脚本已启动。每 {FETCH_INTERVAL} 秒检查一次。")
    while True:
        try:
            check_servers()
            time.sleep(FETCH_INTERVAL)
        except KeyboardInterrupt:
            log_with_time("🛑 用户停止脚本")
            break
        except Exception as e:
            log_with_time(f"❌ 主循环异常: {e}")
            time.sleep(10)


if __name__ == "__main__":
    main()