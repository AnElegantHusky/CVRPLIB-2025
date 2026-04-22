#!/bin/bash
# cmd.sh — Pure Java CLI test commands. Run from Experiment/ directory.

ROOT=$(dirname "$(pwd)")
INSTANCE="Instances/XL-n1048-k237.vrp"
INIT_SOL="Initial_sols/XL-n1048-k237/20260112_235936.sol"
DB="tmp/test_java.db"
# JAR="$ROOT/AILS2/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar"
# JAR="$ROOT/AILS2_Eoh_Acc_large/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar"
JAR="$ROOT/AILS2_Eoh_Omega2/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar"
# JAR="$ROOT/AILS2_Eoh_Ruin/target/AILS-II-1.0-SNAPSHOT-jar-with-dependencies.jar"

# Init the DB first (Python helper), then run Java directly
# python3 -c "
# from pathlib import Path
# from test_one_run import init_db, preload_init_solution
# import time
# db = Path('$DB')
# db.parent.mkdir(exist_ok=True)
# init_db(db)
# preload_init_solution(db, Path('$INIT_SOL'))
# print('DB ready:', db)
# "

java --enable-native-access=ALL-UNNAMED -jar "$JAR" \
    -file "$INSTANCE" \
    # -sharedDB "$DB" \
    -rounded true \
    -best 0 \
    -limit 60 \
    -crtRunningTime 0 \
    -stoppingCriterion Time \
    -dMax 30 \
    -dMin 15 \
    -gamma 30 \
    -varphi 40 \
    -startTime "$(python3 -c 'import time; print(time.time())')" \
    -etaMax 0.01
