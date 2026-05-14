#!/bin/bash
# Usage:
#   bash run_ablation.sh <instance_name> [minute_sec] [--compile]
#   minute_sec defaults to 1800 (30 * 60)
set -e

if [ -z "$1" ]; then
    echo "Usage: bash run_ablation.sh <instance_name> [minute_sec] [--compile]"
    exit 1
fi
INSTANCE_NAME="$1"
MINUTE_SEC="${2:-1800}"
COMPILE=0
if [ "$2" = "--compile" ] || [ "$3" = "--compile" ]; then
    COMPILE=1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPERIMENT_DIR="$ROOT_DIR/Experiment"

# Step 1: Compile (optional)
if [ "$COMPILE" = "1" ]; then
    echo "=========================================="
    echo "[Step 1] Compiling HGS and AILS2..."
    echo "=========================================="
    bash "$ROOT_DIR/compile.sh"
else
    echo "[Step 1] Skipping compile (pass --compile to enable)"
fi

# Step 2: Run ablation scripts simultaneously
echo "=========================================="
echo "[Step 2] Running ablation experiments in parallel..."
echo "=========================================="

PIDS=()
NAMES=()

run_ablation() {
    local script="$1"
    local name="$(basename "$script" .py)"
    echo "[Start] $name"
    (cd "$EXPERIMENT_DIR" && python "$script" Instances "$INSTANCE_NAME" --minute_sec "$MINUTE_SEC") &
    PIDS+=($!)
    NAMES+=("$name")
}

run_ablation "$EXPERIMENT_DIR/ablation_all_e.py"
run_ablation "$EXPERIMENT_DIR/ablation_all_g.py"
run_ablation "$EXPERIMENT_DIR/ablation_origin.py"
run_ablation "$EXPERIMENT_DIR/ablation_wo_e.py"
run_ablation "$EXPERIMENT_DIR/ablation_wo_ws.py"

# Wait for all and check exit codes
FAILED=()
for i in "${!PIDS[@]}"; do
    if wait "${PIDS[$i]}"; then
        echo -e "\033[32m[Done] ${NAMES[$i]}\033[0m"
    else
        echo -e "\033[31m[Failed] ${NAMES[$i]}\033[0m"
        FAILED+=("${NAMES[$i]}")
    fi
done

if [ ${#FAILED[@]} -ne 0 ]; then
    echo -e "\033[31mAblation experiments failed: ${FAILED[*]}\033[0m"
    exit 1
fi

# Step 3: Convert results to CSV
echo "=========================================="
echo "[Step 3] Running db2csv.py..."
echo "=========================================="
(cd "$EXPERIMENT_DIR" && python db2csv.py "$INSTANCE_NAME")

echo "=========================================="
echo -e "\033[32mAll steps completed successfully.\033[0m"
echo "=========================================="
