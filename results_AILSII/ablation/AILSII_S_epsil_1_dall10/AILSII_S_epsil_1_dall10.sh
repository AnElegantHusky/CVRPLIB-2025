#!/bin/bash

time=(2460 5160 14460)
best=(0 0 0)
instances=(XLTEST-n1048-k139 XLTEST-n2168-k625 XLTEST-n6034-k1234)

mkdir -p results/AILSII_S_epsil_1_dall10

for i in {0..7}; do
    inst=${instances[$i]}

    for j in {1..1}; do     
        echo "Run $j instance $inst"
        java -jar -Xms2000m -Xmx4000m bin/AILSII_S_epsil_1.jar \
             -file XLDemo/${inst}.vrp \
             -rounded true \
             -dMax 10 \
             -dMin 10 \
             -stoppingCriterion Time \
             -limit ${time[$i]} \
             -best ${best[$i]} \
        > results/AILSII_S_epsil_1_dall10/${inst}.csv

        # 添加日志信息
        echo "Completed run $j for instance $inst"
    done
done