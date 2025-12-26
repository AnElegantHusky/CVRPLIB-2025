#!/bin/bash

cd src/AILS2_EoH_Omega

mkdir out\production\AILS-II
javac -d out/production/AILS-II -cp src $(find src -name "*.java")
jar cvfe AILSII.jar SearchMethod.AILSII -C out/production/AILS-II .

cd ../../
cp src/AILS2_EoH_Omega/AILSII.jar bin/AILS2_EoH_Omega.jar