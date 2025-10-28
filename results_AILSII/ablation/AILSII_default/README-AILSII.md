
**-varphi** :  Parameter of the feasibility and local search methods that refers to the maximum cardinality of the set of nearest neighbors of the vertices. The default value is 40. The larger it is, the greater the number of movements under consideration in the methods. 

**-gamma** :  Number of iterations for AILS-II to perform a new adjustment of variable 𝜔. The default value is 30.

**-dMax** : Initial reference distance between the reference solution and the  solution obtained after the local search. The default value is 30.

**-dMin** : Final Reference distance between the reference solution and the solution obtained after the local search. The default value is 15.


## run on windows git bash
cd /c/Users/79430/Desktop/CVRPLIB-2025
bash scripts/AILSIIc.sh