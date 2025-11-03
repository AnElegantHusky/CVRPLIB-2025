# CVRPLIB-2025
由于每个方法需要运行较长时间，最好能各分配一个服务器

编译：
```
sudo chmod +x ./bin/* ./scripts/*
./scripts/compile.sh
```

在三台不同服务器上，分别运行：
```
python run.py AILSII_CPU.jar
python run.py hgs-TV
python run.py filo2
```
