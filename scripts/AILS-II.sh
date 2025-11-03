#!/bin/bash


mkdir out\production\AILS-II
javac -d out/production/AILS-II -cp src $(find src -name "*.java")
jar cvfe AILSII.jar SearchMethod.AILSII -C out/production/AILS-II .

cp src/AILS-II_CPU/AILSII.jar bin/AILSII_CPU.jar