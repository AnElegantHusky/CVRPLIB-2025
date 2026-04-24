#!/bin/bash

# Compile all AILS2 file-version variants in src/
# Run from the repo root: bash src/compile.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

success_list=()
failure_list=()

echo "Starting batch build tasks..."
echo "=========================================="

for dir in "$SCRIPT_DIR"/*/; do
    dir="${dir%/}"
    name="$(basename "$dir")"

    [[ "$name" == AILS2* ]] || [[ "$name" == AILS-II* ]] || continue

    echo "[Building] $name"

    if (
        cd "$dir"
        mkdir -p "out/production/$name"
        javac -d "out/production/$name" -cp src $(find src -name "*.java") && \
        jar cvfe AILSII.jar SearchMethod.AILSII -C "out/production/$name" .
    ); then
        echo -e "\033[32m[Success] $name\033[0m"
        success_list+=("$name")
    else
        echo -e "\033[31m[Failure] $name\033[0m"
        failure_list+=("$name")
    fi
    echo "------------------------------------------"
done

echo -e "\n=========================================="
echo "           Build Summary Report"
echo "=========================================="
echo "Total Tasks: $(( ${#success_list[@]} + ${#failure_list[@]} ))"
echo -e "Success Count: \033[32m${#success_list[@]}\033[0m"
echo -e "Failure Count: \033[31m${#failure_list[@]}\033[0m"

if [ ${#failure_list[@]} -ne 0 ]; then
    echo -e "\nFailed projects:"
    for fail in "${failure_list[@]}"; do
        echo -e "  - \033[31m$fail\033[0m"
    done
else
    echo -e "\n\033[32mAll projects built successfully.\033[0m"
fi
echo "=========================================="
