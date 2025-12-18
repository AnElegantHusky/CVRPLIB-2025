# User guide

## Docker preparation
0. Upload the .tar image file
1. Load the image
2. docker run --init -it -v -d ... in the all_in_one folder
3. docker exec 

## all in one v3.51

0. Download the all_in_one folder
1. Compile FILO2 and HGS-TV in the docker container
2. Package AILS2 in the docker container
3. Update the absolute paths for each algorithm in main_for_all3.py
4. Set the warmup time, update interval, and other hyperparameters
5. Run: python main_for_all3.py <INSTANCE_NAME> <MAX_RUNNING_TIME_MIN> (nohup or screen)

## data analysis
0. Convert the output database file to CSV format using sqlite2csv.py
1. Generate plots from the converted CSV data using plot_csv.py

