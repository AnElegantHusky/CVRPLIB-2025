import argparse
import ast
import sqlite3
import json
import shutil  # [新增] 用于删除文件夹
from pathlib import Path


# ================= 辅助函数 (保持不变) =================

def parse_solution_text(sol_text: str):
    """把 DB 中的 solution TEXT 解析为 routes 列表（兼容 json / literal）。"""
    if sol_text is None or sol_text == "":
        return None
    try:
        return ast.literal_eval(sol_text)
    except Exception:
        try:
            return json.loads(sol_text)
        except Exception:
            return None


def routes_to_sol_file(routes, score, out_path: Path):
    """参考 db2sol.py 的输出格式写 .sol 文件。"""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for idx, route in enumerate(routes):
            route_str = " ".join(map(str, route))
            f.write(f"Route #{idx + 1}: {route_str}\n")
        f.write(f"Cost {score:.6f}\n")


def fetch_topk(conn, algo_name: str, k: int):
    """读取某个 algo 在 solution_history 中最近的 k 条解"""
    cur = conn.cursor()
    # 注意：这里增加了对 global_best 的特殊处理逻辑
    if algo_name == "global_best":
        try:
            # global_best 表结构不同，通常只有一条
            cur.execute("SELECT 'global_best', score, solution, runningtime FROM global_best WHERE id=1")
            return cur.fetchall()
        except:
            return []
    else:
        # 常规 history 表查询
        try:
            query = """
                SELECT algo_name, score, solution, runningtime
                FROM solution_history
                WHERE algo_name = ?
                ORDER BY runningtime DESC
                LIMIT ?
            """
            rows = cur.execute(query, (algo_name, k)).fetchall()
            return rows
        except:
            return []


# ================= 核心导出函数 (已修改) =================

def extract_solutions(db_root_path: Path, output_root_path: Path, target_algos: list, top_k: int = 5):
    """
    核心导出逻辑
    :param db_root_path: log_buffer 根目录 (包含 XL-xxx 文件夹的目录)
    :param output_root_path: 结果保存根目录
    :param target_algos: 要提取的算法列表 (e.g. ['ails2', 'global_best'])
    :param top_k: 每个算法提取前 k 个
    :return: 提取成功的实例数量
    """
    if not db_root_path.exists():
        print(f"[Warn] DB root not found: {db_root_path}")
        return 0

    # [新增/修改] 清理旧的输出目录
    if output_root_path.exists():
        print(f"[Info] Cleaning old output directory: {output_root_path}")
        try:
            shutil.rmtree(output_root_path)
        except Exception as e:
            print(f"[Error] Failed to clean directory {output_root_path}: {e}")
            return 0

    # 重新创建目录
    output_root_path.mkdir(parents=True, exist_ok=True)

    success_count = 0

    # 遍历所有实例目录 (XL-*)
    for inst_dir in sorted(db_root_path.iterdir()):
        if not inst_dir.is_dir() or not inst_dir.name.startswith("XL-"):
            continue

        db_path = inst_dir / "shared.db"
        if not db_path.exists():
            continue

        try:
            # 使用只读模式连接
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            any_saved = False

            # 如果 target_algos 为空，则自动查找所有 algo (可选功能，这里保持明确指定)
            algos_to_run = target_algos

            for algo in algos_to_run:
                rows = fetch_topk(conn, algo, top_k)
                if not rows:
                    continue

                for rank, (algo_name, score, sol_text, runningtime) in enumerate(rows, start=1):
                    routes = parse_solution_text(sol_text)
                    if routes is None:
                        continue

                    # 路径结构: output / Instance / Algo / rank.sol
                    out_path = output_root_path / inst_dir.name / algo / f"{rank}.sol"
                    routes_to_sol_file(routes, score, out_path)
                    any_saved = True

            conn.close()
            if any_saved:
                success_count += 1
                # print(f"[Extract] {inst_dir.name} OK")

        except Exception as e:
            print(f"[Error] {inst_dir.name}: {e}")

    return success_count


# ================= 命令行入口 (保持原有功能) =================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Extract solutions from DB")
    parser.add_argument("--algos", nargs="+", default=["ails2", "sisr_cvrp", "global_best"], help="List of algo names")
    parser.add_argument("--topk", type=int, default=5, help="Top K latest solutions")
    parser.add_argument("--root_dir", type=str, default=".", help="Root dir containing SISR/log_buffer")

    args = parser.parse_args()

    root_path = Path(args.root_dir).resolve()
    # 推导默认路径
    log_root = root_path / "SISR" / "log_buffer"
    out_root = root_path / "SISR" / "ails2_ext_sols"

    print(f"Extracting from {log_root} to {out_root}...")
    cnt = extract_solutions(log_root, out_root, args.algos, args.topk)
    print(f"Done. Processed {cnt} instances.")

    # example usage:
    # EXTRACT_ALGOS = [
    #     "ails2_etaMax1.000_stoppingTime86400.00",  # 1 天
    #     "ails2_etaMax1.000_stoppingTime432000.00",  # 5 天
    #     "ails2_etaMax1.000_stoppingTime864000.00",  # 10 天
    #     "ails2_etaMax1.000_stoppingTime1728000.00",  # 20 天
    # ]
    # extract_solution('SISR/log_buffer', 'SISR/ails2_ext_sols', EXTRACT_ALGOS, top_k=5)

    # results -> SISR/ails2_ext_sols/XL-xxx/ails2_xxx/1.sol, 2.sol, ...