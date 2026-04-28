python ./pipeline.py --time-limit 60 --index-start 0 --index-end 2 --eta-max 0.01

python ./test_one_run.py --algo AILS2 --instance /home/chenxin/CVRPLIB-2025/Experiment_sol/Instances/XL-n10001-k1570.vrp --time-limit 3600 --output-dir /home/chenxin/CVRPLIB-2025/Experiment_sol/test --verbose 

python ./test_one_run.py --algo AILS2 --instance /home/chenxin/CVRPLIB-2025/Experiment_sol/Instances/XL-n5061-k184.vrp --time-limit 3600 --output-dir /home/chenxin/CVRPLIB-2025/Experiment_sol/test --verbose 

python ./test_one_run.py --algo AILS2 --instance /home/chenxin/CVRPLIB-2025/Experiment_sol/Instances/XL-n9784-k2774.vrp --time-limit 3600 --output-dir /home/chenxin/CVRPLIB-2025/Experiment_sol/test --verbose 

python ./pipeline.py --time-limit 10 --index-start 10 --index-end 12 --eta-max 0.01 

python ./pipeline.py --time-limit 10 --index-start 0 --index-end 1 --eta-max 0.01 --load-initial

python ./pipeline.py --time-limit 3600 --index-start 0 --index-end 1 --eta-max 0.01 --load-initial

python ./test_one_run.py --algo AILS2_Eoh_Ruin2 --instance /home/chenxin/CVRPLIB-2025/Experiment_sol/Instances/XL-n1048-k237.vrp --time-limit 3600 --output-dir /home/chenxin/CVRPLIB-2025/Experiment_sol/test --verbose 

python ./test_one_run.py --algo AILS2_Eoh_Ruin --instance /home/chenxin/CVRPLIB-2025/Experiment_sol/Instances/XL-n1048-k237.vrp --time-limit 3600 --output-dir /home/chenxin/CVRPLIB-2025/Experiment_sol/test --verbose 