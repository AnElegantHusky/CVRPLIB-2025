
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

## 2 运行命令

### 2.1 
```bash
python pipeline_bath_push.py --sol_dir ./mahdi_bks
```

[//]: # (### 2.2 上传 bks)

[//]: # (```bash)

[//]: # (python pipeline_bath_push.py --sol_dir ./mahdi_bks)

[//]: # (```)

[//]: # ()
[//]: # (### 2.3 获取监控日志)

[//]: # (```bash)

[//]: # (python pipeline_download_files.py service_ingest.log --type main)

[//]: # (python pipeline_monitor.py)

[//]: # (```)

[//]: # ()
[//]: # (### 2.4 传输文件路径)

[//]: # (```bash)

[//]: # (downloaded_files)

[//]: # (logs_monitor)

[//]: # (```)




