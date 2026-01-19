import argparse
import ast
import sqlite3
from pathlib import Path


def parse_solution_text(sol_text: str):
    """把 DB 中的 solution TEXT 解析为 routes 列表（兼容 json / literal）。"""
    if sol_text is None or sol_text == "":
        return None
    try:
        return ast.literal_eval(sol_text)
    except Exception:
        try:
            import json
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
    """
    读取某个 algo 在 solution_history 中最近的 k 条解：
    - 按 runningtime DESC（最近）优先
    """
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT algo_name, score, solution, runningtime
        FROM solution_history
        WHERE algo_name = ?
        ORDER BY runningtime DESC
        LIMIT ?
        """,
        (algo_name, k),
    ).fetchall()
    return rows


def main():
    parser = argparse.ArgumentParser(description="Extract survivor solutions to sol files.")
    parser.add_argument("--topk", type=int, default=3, help="每个算法保留最近的 k 个解（按 runningtime DESC）")
    parser.add_argument(
        "--algos",
        nargs="+",
        # AILS2 在 DB 中保存的 algo_name 形如：ails2_etaMaxX.XXX_stoppingTimeYYYYY.YY
        default=[
            "ails2_etaMax1.000_stoppingTime86400.00",        # 1 天
            "ails2_etaMax1.000_stoppingTime432000.00",       # 5 天
            "ails2_etaMax1.000_stoppingTime864000.00",       # 10 天
            "ails2_etaMax1.000_stoppingTime1728000.00",      # 20 天
            "ails2_eoh_omega2"
            "ails2_etaMax0.010_stoppingTime432000.00",
        ],
        help="要提取的算法名称列表（solution_history.algo_name），默认已对齐 AILSII 的命名规则",
    )
    args = parser.parse_args()

    # 路径
    sisr_path = Path(__file__).resolve().parent
    root_path = sisr_path.parent
    log_root = root_path / "SISR" / "log_buffer"
    out_root = root_path / "SISR" / "ails2_ext_sols"
    out_root.mkdir(parents=True, exist_ok=True)

    for inst_dir in sorted(log_root.iterdir()):
        if not inst_dir.is_dir():
            continue
        db_path = inst_dir / "shared.db"
        if not db_path.exists():
            continue

        try:
            conn = sqlite3.connect(db_path)
            any_saved = False
            for algo in args.algos:
                rows = fetch_topk(conn, algo, args.topk)
                if not rows:
                    continue
                for rank, (algo_name, score, sol_text, runningtime) in enumerate(rows, start=1):
                    routes = parse_solution_text(sol_text)
                    if routes is None:
                        continue
                    out_path = out_root / inst_dir.name / algo_name / f"{rank}.sol"
                    routes_to_sol_file(routes, score, out_path)
                    any_saved = True
            if any_saved:
                print(f"[OK] {inst_dir.name} -> {out_root/inst_dir.name}")
            else:
                print(f"[Skip] {inst_dir.name}: no valid solutions")
        except Exception as e:
            print(f"[Fail] {inst_dir.name}: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()

