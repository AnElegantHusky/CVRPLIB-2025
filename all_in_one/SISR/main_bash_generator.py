from pathlib import Path


SISR_PATH = Path(__file__).resolve().parent
ROOT_PATH = SISR_PATH.parent

instance_folder = 'cvrplib_1019' # TODO: check path
instance_root_path = SISR_PATH / 'data' / instance_folder

sh_name = 'run_all.sh'

lines = [
    "#!/bin/bash",
    "",
]
for instance_path in instance_root_path.rglob('*.vrp'):
    instance_name = instance_path.name
    cmd = f"nohup python main_for_all_final.py {instance_folder} {instance_name} > {instance_name}.log 2>&1 &"
    lines.append(cmd)

with open(sh_name, 'w', encoding='utf-8') as f:
    f.write("\n".join(lines))
    f.write("\n")  # 文件末尾加个换行是个好习惯

