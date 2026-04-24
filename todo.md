AILS2 is the algorithm backbone for CVRP.

I have multiple variants of AILS2, and for each variant I have two version: 

1. Use SQLite database to store results / load initial solutions
2. Use .sol and .csv file to store results / load initial solutions

| variant name | db version | file version | description |
| --- | --- | --- | --- |
| AILS2 | ./AILS2 | src/AILS-II_origin: run from start; src/AILS2-II_continue: warm start | --- |
| AILS2_EoH_Acc | ./AILS2_Eoh_Acc | src/AILS2_EoH_Acc | compared with AILS2, acceptance criterion is changed in DiversityControl |
| AILS2_EoH_Acc_large | ./AILS2_Eoh_Acc_large | src/AILS2_EoH_Acc_large | compared with AILS2, acceptance criterion is changed in DiversityControl |
| AILS2_EoH_Omega2 | ./AILS2_Eoh_Omega2 | src/AILS2_EoH_Omega2 | the omega control is modified in DiversityControl |
| AILS2_EoH_Ruin | ./AILS2_Eoh_Ruin | src/AILS2_EoH_Ruin | new perturbation algorithm added in Perturbation |


In Experiment/pipeline.py, I tried to use the db version to run the experiment, but encounter problem. Now I want to use the file version to rewrite the experiment pipeline.

Taske:
1. make sure the file version source code have the same algorithm logic with db version (focus on the files that are different from original AILS2); especially, make sure that AILS2_EoH_Ruin is correct
2. Use Experiment/pipeline.py as reference, write Experiment_sol/pipeline.py:
   1. You can use run_ails2_parallel_continue.py as reference for how to pass initial solutions to other methods, or how to run from scratch. Modify Experiment_sol/test_one_run.py to fit file version.
   2. Use AILS-II_origin for generating initial solutions in step 2. the .sol files are stored in Experiment_sol/Initial_sols, the solution log csv files are stored in Experiment_sol/results/{method}/{instance}.csv
   3. In step 3, algorithms read initial solutions from Initial_sols, and store finial solutions in Experiment_sol/results_sols/{method}/{instance}.csv; csv results in Experiment_sol/results/{method}/{instance}.csv
   4. please check the csv content for file version: all solution scores are recorded, or only improvement scores are recorded?
   
   