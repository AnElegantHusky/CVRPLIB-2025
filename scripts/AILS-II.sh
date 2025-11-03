#!/bin/bash


mkdir out\production\AILS-II
javac -d out\production\AILS-II -cp src (Get-ChildItem src -Filter *.java -Recurse).FullName
jar cvfe AILSII.jar SearchMethod.AILSII -C out\production\AILS-II .

cp src/AILS-II_CPU/AILSII.jar bin/AILSII_CPU.jar