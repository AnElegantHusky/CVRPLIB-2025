#!/bin/bash
# Run from project root: bash compile.sh
set -e

MAVEN_SSL_OPTS="-Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

success_list=()
failure_list=()

build() {
    local name="$1"
    local dir="$ROOT_DIR/$name"
    local cmd="$2"
    echo "=========================================="
    echo "[Building] $name"
    if (cd "$dir" && eval "$cmd"); then
        echo -e "\033[32m[Success] $name\033[0m"
        success_list+=("$name")
    else
        echo -e "\033[31m[Failure] $name\033[0m"
        failure_list+=("$name")
    fi
}

# --- AILS2 variants (Maven) ---
for dir in "$ROOT_DIR"/AILS2*/; do
    name="$(basename "$dir")"
    build "$name" "mvn clean package $MAVEN_SSL_OPTS"
done

# --- HGS-TV (CMake) ---
build "HGS-TV" "cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --parallel"

# --- Summary ---
echo "=========================================="
echo "           Build Summary"
echo "=========================================="
echo "Success (${#success_list[@]}): ${success_list[*]}"
echo "Failure (${#failure_list[@]}): ${failure_list[*]}"
if [ ${#failure_list[@]} -eq 0 ]; then
    echo -e "\033[32mAll builds succeeded.\033[0m"
else
    echo -e "\033[31mSome builds failed.\033[0m"
    exit 1
fi
