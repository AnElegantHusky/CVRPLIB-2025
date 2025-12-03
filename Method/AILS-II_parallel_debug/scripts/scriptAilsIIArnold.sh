#!/bin/bash

time=( "5" "5" "5" "5" "5" "5" "5" "5" "5" "5" )

instances=(  "Antwerp1" "Antwerp2" "Brussels1" "Brussels2" "Flanders1" "Flanders2" "Ghent1" "Ghent2" "Leuven1" "Leuven2")

for i in {0..9};
do
	for j in {1..10};
	do
		echo "Run $j instance ${instances[$i]}"
		java -jar -Xms2000m -Xmx4000m AILSII_CPU_OUTSOL.jar -file CVRP/Instances/${instances[$i]}.vrp -rounded true -stoppingCriterion Time -limit ${time[$i]} > Results/${instances[$i]}.txt
	done
done

