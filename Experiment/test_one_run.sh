python test_one_run.py \
      --algo AILS2 \
      --instance Instances/XL-n1048-k237.vrp \
      --init-sol Initial_sols/XL-n1048-k237/20260112_235936.sol \
      --output results/test/XL-n1048-k237__20260112_235936__AILS2.csv \
      --time-limit 60 --verbose --eta-max 0.01

python test_one_run.py  --algo AILS2 --instance Instances/XL-n1048-k237.vrp --output results/test/XL-n1048-k237__none__AILS2.csv --time-limit 6000 --verbose


python test_one_run.py --algo AILS2  --instance Instances/XL-n1048-k237.vrp --init-sol Initial_sols/XL-n1048-k237/20260112_235936.sol  --output results/test/XL-n1048-k237__20260112_235936__AILS2.csv   --time-limit 6000 --verbose --eta-max 0.01
