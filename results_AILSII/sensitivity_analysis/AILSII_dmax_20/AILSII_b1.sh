#!/bin/bash

time=(14460)
best=(1234)
instances=(XLTEST-n6034-k1234)

mkdir -p results/AILSII_b1

for i in {0..1}; do
    inst=${instances[$i]}

    for j in {1..1}; do     
        echo "Run $j instance $inst"
        java -jar -Xms2000m -Xmx4000m bin/AILSII.jar \
             -file XLDemo/${inst}.vrp \
             -rounded true \
             -dMax 20 \
             -stoppingCriterion Time \
             -limit ${time[$i]} \
             -best ${best[$i]} \
        > results/AILSII_b1/${inst}.csv

        # 添加日志信息
        echo "Completed run $j for instance $inst"
    done
done