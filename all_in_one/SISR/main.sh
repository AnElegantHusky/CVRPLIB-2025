#!/bin/bash

#rm -rf ./log_buffer

rm -rf ./data/instances

unzip -o instances.zip -d ./data/instances

docker exec -w /app cvrplib bash -c "cd all_in_one/SISR && python3 main_bash_generator.py $1 $2 && bash run_all.sh"