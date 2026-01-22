from extract_survivor_history import extract_solutions
from pathlib import Path

if __name__ == "__main__":
    CVRP = Path("/cvrplib_link")
    WS = Path("./")

    DB_DIR = CVRP / "log_buffer"
    EXT_DIR = WS / "test_extract"
    EXTRACT_ALGOS = [
        "ails2_etaMax1.000_stoppingTime86400.00",  # 1 天
        "ails2_etaMax1.000_stoppingTime432000.00",  # 5 天
        "ails2_etaMax1.000_stoppingTime864000.00",  # 10 天
        "ails2_etaMax1.000_stoppingTime1296000.00",      # 15 天
        "ails2_etaMax1.000_stoppingTime1728000.00",      # 20 天
    ]

    count = extract_solutions(DB_DIR, EXT_DIR, EXTRACT_ALGOS, top_k=5)

