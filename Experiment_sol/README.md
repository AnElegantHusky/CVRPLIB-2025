请在不同服务器上运行以下命令：

```bash
cd Experiment_sol

nohup python ./pipeline.py --time-limit 86400 --index-start 0 --index-end 20 --eta-max 0.01 > output.log 2>&1 &  # server 1, 100 processes
nohup python ./pipeline.py --time-limit 86400 --index-start 20 --index-end 40 --eta-max 0.01 > output.log 2>&1 &  # server 2, 100 processes
nohup python ./pipeline.py --time-limit 86400 --index-start 40 --index-end 60 --eta-max 0.01 > output.log 2>&1 &  # server 3, 100 processes
nohup python ./pipeline.py --time-limit 86400 --index-start 60 --index-end 80 --eta-max 0.01 > output.log 2>&1 &  # server 4, 100 processes
nohup python ./pipeline.py --time-limit 86400 --index-start 80 --index-end 100 --eta-max 0.01 > output.log 2>&1 &  # server 5, 100 processes

```
每台服务器上进程数：(index-end - index-start) * 5。可根据服务器资源数调整index-start和index-end，只需要保证100个index都覆盖到即可。

结果路径：Experiment_sol/results
运行时间：总共两天