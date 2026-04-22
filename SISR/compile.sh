#!/bin/bash

# Define Maven SSL ignore options
MAVEN_SSL_OPTS="-Dmaven.wagon.http.ssl.insecure=true -Dmaven.wagon.http.ssl.ignore.validity.dates=true"

# Arrays to track results
success_list=()
failure_list=()

echo "Starting batch build tasks..."
echo "=========================================="

# Iterate through all directories in the current path
for dir in */; do
    dir=${dir%/} # Remove trailing slash

    # Check if it is a directory (exclude script itself or files)
    [ -d "$dir" ] || continue

    cmd=""
    # Determine execution command based on directory name
    if [[ "$dir" == HGS* ]] || [[ "$dir" == "FILO2" ]]; then
        cmd="bash rebuild_sy.sh"
    elif [[ "$dir" == AILS2* ]]; then
        cmd="mvn clean package $MAVEN_SSL_OPTS"
    else
        continue # Skip if not a target directory
    fi

    echo "[Building] Directory: $dir"
    echo "Executing command: $cmd"

    # Execute in a sub-shell and capture exit status ($?)
    # Using (cd ... && ...) ensures the directory change doesn't affect the main script
    if (cd "$dir" && eval "$cmd"); then
        echo -e "\033[32m[Success] $dir build completed\033[0m"
        success_list+=("$dir")
    else
        echo -e "\033[31m[Failure] Error occurred during build of $dir\033[0m"
        failure_list+=("$dir")
    fi
    echo "------------------------------------------"
done

# --- Final Summary Report ---
echo -e "\n=========================================="
echo "           Build Summary Report"
echo "=========================================="
echo "Total Tasks: $(( ${#success_list[@]} + ${#failure_list[@]} ))"
echo -e "Success Count: \033[32m${#success_list[@]}\033[0m"
echo -e "Failure Count: \033[31m${#failure_list[@]}\033[0m"

if [ ${#failure_list[@]} -ne 0 ]; then
    echo -e "\nThe following projects failed to build. Please check logs:"
    for fail in "${failure_list[@]}"; do
        echo -e "  - \033[31m$fail\033[0m"
    done
else
    echo -e "\n\033[32mCongratulations! All projects built successfully.\033[0m"
fi
echo "=========================================="