#!/bin/bash

rm -rf ./log_buffer

unzip -o instances.zip -d ./data/instances

docker exec -w /app cvrplib bash -c "python3 main_bash_generator.py $1 $2 && bash run_all.sh"