## Description

AILS-II is an Adaptive Iterated Local Search (AILS) meta-heuristic that embeds adaptive strategies to tune  diversity control parameters. These parameters are the perturbation degree and the acceptance criterion. They are key parameters to ensure that the method escapes from local optima and keeps an adequate level of exploitation and exploration of the method. Its implementation is in JAVA language.

## To run the algorithm

```console
java -jar AILSII.jar -file data/X-n214-k11.vrp -rounded true -best 10856 -limit 100 -stoppingCriterion Time 
```

# 创建输出目录
mkdir out\production\AILS-II

# 编译代码
javac -d out\production\AILS-II -cp src (Get-ChildItem src -Filter *.java -Recurse).FullName

# 打包 JAR 文件
jar cvfe AILSII.jar SearchMethod.AILSII -C out\production\AILS-II .

# 测
java -jar AILSII.jar -file XLDemo/XLTEST-n1048-k139.vrp -rounded true -best 10856 -limit 100 -stoppingCriterion Time 

Run the AILSII class that has the following parameters:

**-file** : the file address of the problem instance.

**-rounded** :  A flag that indicates whether the instance has rounded distances or not. The options are: [false, true]. The default value is true.

**-stoppingCriterion** : It is possible to use two different stopping criteria:
* **Time** : The algorithm stops when a given time in seconds has elapsed; 
* **Iteration** :  The algorithm stops when the given number of iterations has been reached. 

**-limit** : Refers to the value that will be used in the stopping criterion. If the stopping criterion is a time limit, this parameter is the timeout in seconds. Otherwise, this parameter indicates the number of iterations. The default value is the maximum limit for a double precision number in the JAVA language (Double.MAX_VALUE).

**-best** :  Indicates the value of the optimal solution. The default value is 0.

**-varphi** :  Parameter of the feasibility and local search methods that refers to the maximum cardinality of the set of nearest neighbors of the vertices. The default value is 40. The larger it is, the greater the number of movements under consideration in the methods. 

**-gamma** :  Number of iterations for AILS-II to perform a new adjustment of variable 𝜔. The default value is 30.

**-dMax** : Initial reference distance between the reference solution and the  solution obtained after the local search. The default value is 30.

**-dMin** : Final Reference distance between the reference solution and the solution obtained after the local search. The default value is 15.

**-decoEnable** : Decide use or not use decomposition, can be selected from ['true', 'false'], default value is true.

**-stagnationThreshold** After how many iterations to use decompostion, default value is 5000.
