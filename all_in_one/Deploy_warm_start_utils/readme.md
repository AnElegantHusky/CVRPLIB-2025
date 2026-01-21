
## 1 环境要求

1.1 python
```bash
pip install fabric
```

1.2 能连接以下服务器
```bash
10.90.91.100,
10.90.91.101,
10.90.91.124,
10.90.91.125,
10.90.91.126,
10.90.91.127,
10.90.91.163,
10.90.91.167,
10.90.91.49,
10.90.91.51,
10.90.91.231,
10.90.91.232,
```

## 2 运行

2.1 路径
```bash
cd all_in_one/Deploy_warm_start_utils
```

2.2 运行
```bash
python pipeline_restart.py
python pipeline_monitor.py
```

2.3 传输结果
```bash
10.90.91.232: 
 - /home/cvrp/cvrp_com_hyb/Competition_Deploy_Hybird/all_in_one/SISR/ails2_ext_sols
本地: logs_monitor
```