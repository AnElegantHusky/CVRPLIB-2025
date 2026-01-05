# CVRPLIB-2025

# 编译
```
sudo chmod +x ./scripts/*
./scripts/compile.sh
sudo chmod +x ./bin/* 
```


[//]: # (```)

[//]: # (python run.py AILSII_CPU.jar)

[//]: # (python run.py hgs-TV)

[//]: # (python run.py filo2)

[//]: # (```)

[//]: # (测试命令（仅跑前10个实例，每个方法限时10秒）)

[//]: # (```)

[//]: # (python run.py AILSII_origin.jar --start-idx 0 --end-idx 10 --time-limit 10)

[//]: # (python run.py AILSII_perturbation1.jar --start-idx 0 --end-idx 10 --time-limit 10)

[//]: # (python run.py AILSII_perturbation2.jar --start-idx 0 --end-idx 10 --time-limit 10)

[//]: # (python run.py AILSII_deco.jar --start-idx 0 --end-idx 10 --time-limit 10)

[//]: # (```)


# 请在不同服务器上分别运行以下命令

[//]: # (345600)

```

nohup python run_ails2_parallel_etacycle_continue.py --start_idx 0 --end_idx 48 > output.log 2>&1 &

```

```

nohup python run_ails2_parallel_etacycle_continue.py --start_idx 48 --end_idx 96 > output.log 2>&1 &

```

[//]: # (```)

[//]: # ()
[//]: # (nohup python run.py AILS2_EoH_Acc.jar --start-idx 0 --end-idx 50 --time-limit 345600 > output.log 2>&1 &)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (nohup python run.py AILS2_EoH_Acc.jar --start-idx 50 --end-idx 100 --time-limit 345600 > output.log 2>&1 &)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (nohup python run.py AILS2_EoH_Omega.jar --start-idx 0 --end-idx 50 --time-limit 345600 > output.log 2>&1 &)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (nohup python run.py AILS2_EoH_Omega.jar --start-idx 50 --end-idx 100 --time-limit 345600 > output.log 2>&1 &)

[//]: # ()
[//]: # (```)

[//]: # (```)

[//]: # ()
[//]: # (python run.py AILSII_origin_wall.jar --start-idx 0 --end-idx 50 --time-limit 86400)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (python run.py AILSII_origin_wall.jar --start-idx 50 --end-idx 100 --time-limit 86400)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (```)

[//]: # ()
[//]: # (python run_ails2_parallel_threading.py)

[//]: # ()
[//]: # (```)
