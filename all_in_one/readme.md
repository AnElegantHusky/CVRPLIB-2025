# User guide

## Docker preparation
0. Upload .tar
1. Load image
2. docker run --init -it -v -d ... in all_in_one
3. docker exec 

## all in one v3.51

0. Download all_in_one folder
1. Build FILO2 and HGS-TV in the docker container
2. Package AILS2 in the docker container
3. Set the path of each algorithms in main_for_all3.py
4. Set the warmup time, update interval, and other hyperparameters
5. Run: python main_for_all3.py INSTANCE_NAME MAX_RUNNING_TIME_MIN (nohup or screen)

## data analysis
0. convert .db to .csv using sqlite2csv.py
1. plot .csv using plot_csv.py

