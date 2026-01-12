
## 1 部署（详见跳板机文件）
```angular2html
cd Competition_Deploy_Hybird
docker run --init -it -d -v $(pwd):/app --name cvrplib cvrplib_sy5
docker exec -it cvrplib bash

bash compile.sh

cd SISR
python -m pip install -r requirements2.txt

python3 main_bash_generator.py 6 8

bash run_all.sh

```

## 2 运行
```bash
docker exec -w /app/SISR cvrplib bash -c "python3 main_bash_generator.py 6 8 && bash run_all.sh"

```

## 3 docker容器操作
查看容器（容器名固定cvrplib）
```bash
docker ps | grep "cvrplib"

```

进入正在后台运行中的容器
```bash
docker exec -it cvrplib bash

```

关闭容器中任务，但不杀死容器
```bash
# 杀死容器 cvrplib 内所有名为 python3 的进程
docker exec cvrplib pkill -f python3

# 如果上面那个没停干净，可以杀掉 shell 脚本
docker exec cvrplib pkill -f run_all.sh
```

