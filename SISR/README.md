# CVRPLIB Competition

## 1 上传与运行

### 1.1 instances.zip 打包
instances.zip: 直接包含所有*.vrp文件。不要放在instances文件夹下再压缩。放在SISR文件夹下

### 1.2 server_send_files.py 上传文件

需要提前安装fabric库
```bash
pip install fabric
```

运行以下命令，批量上传文件到所有服务器。`file_name_list`定义了上传文件列表，目前为instances.zip。`servers`定义了服务器列表
```bash
python server_send_files.py 
```

### 1.3 server_send_cmd.py 启动计算
```bash
python server_send_cmd.py
```