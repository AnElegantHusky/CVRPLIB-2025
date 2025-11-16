## 编译jar==========================================================================================================================================================
# 创建输出目录
mkdir out\production\AILS-II

# 编译代码
javac -d out\production\AILS-II -cp src (Get-ChildItem src -Filter *.java -Recurse).FullName

# 打包 JAR 文件
jar cvfe AILSII.jar SearchMethod.AILSII -C out\production\AILS-II .

# 测
java -jar AILSII.jar -file XLDemo/XLTEST-n1048-k139.vrp -rounded true  -limit 3 -stoppingCriterion Time


## To run the algorithm===============================================================================================================================================

java -jar bin/AILSII.jar -file XLDemo/XLTEST-n1048-k139.vrp -best 139 -limit 1 -stoppingCriterion Time 

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


## Description============================================================================================================================================================
[1] Máximo, Vinícius R., Nascimento, Mariá C.V. (2021).
A hybrid adaptive iterated local search with diversification control to the capacitated vehicle routing problem. European Journal of Operational Research, Volume 294, p. 1108-1119, https://doi.org/10.1016/j.ejor.2021.02.024 (also available at [aXiv](https://arxiv.org/abs/2012.11021)).

[2] Máximo, Vinícius R., Cordeau, Jean-François, Nascimento, Mariá C.V. (2022).
An adaptive iterated local search heuristic for the Heterogeneous Fleet Vehicle Routing Problem. Computers & Operations Research, Volume 148, p. 105954.
https://doi.org/10.1016/j.cor.2022.105954 (also available at [aXiv](https://arxiv.org/abs/2111.12821)).

AILS-II is an Adaptive Iterated Local Search (AILS) meta-heuristic that embeds adaptive strategies to tune  diversity control parameters. These parameters are the perturbation degree and the acceptance criterion. They are key parameters to ensure that the method escapes from local optima and keeps an adequate level of exploitation and exploration of the method. Its implementation is in JAVA language.

## run on windows git bash=================================================================================================================================================

cd /c/Users/79430/Desktop/CVRPLIB-2025
bash scripts/AILSII.sh


## 输出=====================================================================================================================================================================
新代码中包含两种输出，一种是只输出最终解（默认），另一种是输出每一步有提升的解（可能会占用大量存储空间）
每个instance都输出在Results/{instance_name}文件夹下，solution的文件名为时间， 其他信息的文件名为{instance}.csv

# 输出每次的解和最终解的开关在AILSIIj.java 82行：
boolean outputAllSteps = false; // 这里设置为false只输出最终解

# 若想要输出时间和besfF外的其他值，请替换AILSIIj.java 中366, 372行中的参数如下，参数可自由选取：
				"solution quality: "+bestF
				+" gap: "+deci.format(getGap())+"%"
				+" K: "+solution.numRoutes
				+" iteration: "+iterator
				+" eta: "+deci.format(acceptanceCriterion.getEta())
				+" omega: "+deci.format(selectedPerturbation.omega)
				+" time: "+timeAF