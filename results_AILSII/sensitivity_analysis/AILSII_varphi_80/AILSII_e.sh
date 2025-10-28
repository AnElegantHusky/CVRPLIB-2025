#!/bin/bash

time=(7440)
best=(685)
instances=(XLTEST-n3101-k685)

mkdir -p results/AILSII_e

for i in {0..1}; do
    inst=${instances[$i]}

    for j in {1..1}; do     
        echo "Run $j instance $inst"
        java -jar -Xms2000m -Xmx4000m bin/AILSII.jar \
             -file XLDemo/${inst}.vrp \
             -rounded true \
             -varphi 80 \
             -stoppingCriterion Time \
             -limit ${time[$i]} \
             -best ${best[$i]} \
        > results/AILSII_e/${inst}.csv

        # 添加日志信息
        echo "Completed run $j for instance $inst"
    done
done