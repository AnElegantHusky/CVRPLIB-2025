#!/bin/bash

time=(2460 5160 7440 10140 12360 13500 14460 20580)
best=(139 625 685 164 170 365 1234 343)
instances=(XLTEST-n1048-k139 XLTEST-n2168-k625 XLTEST-n3101-k685 XLTEST-n4245-k164 XLTEST-n5174-k170 XLTEST-n5649-k365 XLTEST-n6034-k1234 XLTEST-n8575-k343)

mkdir -p results/AILSII_CPU

for i in {0..7}; do
    inst=${instances[$i]}

    for j in {1..1}; do     
        echo "Run $j instance $inst"
        java -jar -Xms2000m -Xmx4000m bin/AILSII.jar \
             -file XLDemo/${inst}.vrp \
             -rounded true \
             -stoppingCriterion Time \
             -limit ${time[$i]} \
             -best ${best[$i]} 

        # 添加日志信息
        echo "Completed run $j for instance $inst, results saved to Results folder"
    done
done