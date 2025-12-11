/**
 * 	Copyright 2022, Vinícius R. Máximo
 *	Distributed under the terms of the MIT License. 
 *	SPDX-License-Identifier: MIT
 */
package SearchMethod;

import java.lang.reflect.InvocationTargetException;
import java.text.DecimalFormat;
import java.time.Instant;
import java.util.HashMap;
import java.util.Random;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.io.File;
import java.io.FileWriter;
import java.io.IOException;
import java.util.List;
import java.util.ArrayList;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.io.FilenameUtils;
import java.util.Map;

import Auxiliary.Distance;
import Data.Instance;
import DiversityControl.DistAdjustment;
import DiversityControl.OmegaAdjustment;
import DiversityControl.AcceptanceCriterion;
import DiversityControl.IdealDist;
import Improvement.LocalSearch;
import Improvement.IntraLocalSearch;
import Improvement.FeasibilityPhase;
import Perturbation.InsertionHeuristic;
import Perturbation.Perturbation;
import Solution.Solution;

public class AILSII
{
	//----------Problema------------
	Solution solution,referenceSolution,bestSolution;
	List<Integer> initSolutionList;
    double startTime;
	Instance instance;
	Distance pairwiseDistance;
	double bestF=Double.MAX_VALUE;
	double executionMaximumLimit;
	double optimal;

	//----------caculoLimiar------------
	int numIterUpdate;

	//----------Metricas------------
	int iterator,iteratorMF;
	long first,ini;
	double timeAF,totalTime,time;

	Random rand=new Random();

	HashMap<String,OmegaAdjustment>omegaSetup=new HashMap<String,OmegaAdjustment>();

	double distanceLS;

	Perturbation[] pertubOperators;
	Perturbation selectedPerturbation;

	FeasibilityPhase feasibilityOperator;
	ConstructSolution constructSolution;

	LocalSearch localSearch;

	InsertionHeuristic insertionHeuristic;
	IntraLocalSearch intraLocalSearch;
	AcceptanceCriterion acceptanceCriterion;
//	----------Mare------------
	DistAdjustment distAdjustment;
//	---------Print----------
	boolean print=true;
	IdealDist idealDist;

	double epsilon;
	DecimalFormat deci=new DecimalFormat("0.0000");
	StoppingCriterionType stoppingCriterionType;
//	---------DB OUTPUT----------

    String sharedDB;
    Instant preUpdate;
    long updateInterval;

    public AILSII(Instance instance,InputParameters reader)
	{
		this.instance=instance;

        this.sharedDB = reader.getSharedDB();
        this.preUpdate = Instant.now();
        this.updateInterval = 5;

        this.startTime = reader.getStartTime();

		Config config=reader.getConfig();
		this.optimal=reader.getBest();
		this.executionMaximumLimit=reader.getTimeLimit();

		this.epsilon=config.getEpsilon();
		this.stoppingCriterionType=config.getStoppingCriterionType();
		this.idealDist=new IdealDist();
		this.solution =new Solution(instance,config);
		this.referenceSolution =new Solution(instance,config);
		this.bestSolution =new Solution(instance,config);
		this.numIterUpdate=config.getGamma();

		this.pairwiseDistance=new Distance();

		this.pertubOperators=new Perturbation[config.getPerturbation().length];

		this.distAdjustment=new DistAdjustment( idealDist, config, executionMaximumLimit);

		this.intraLocalSearch=new IntraLocalSearch(instance,config);

		this.localSearch=new LocalSearch(instance,config,intraLocalSearch);

		this.feasibilityOperator=new FeasibilityPhase(instance,config,intraLocalSearch);

		this.constructSolution=new ConstructSolution(instance,config);

		OmegaAdjustment newOmegaAdjustment;
		for (int i = 0; i < config.getPerturbation().length; i++)
		{
			newOmegaAdjustment=new OmegaAdjustment(config.getPerturbation()[i], config,instance.getSize(),idealDist);
			omegaSetup.put(config.getPerturbation()[i]+"", newOmegaAdjustment);
		}

		this.acceptanceCriterion=new AcceptanceCriterion(instance,config,executionMaximumLimit);

		try
		{
			for (int i = 0; i < pertubOperators.length; i++)
			{
				this.pertubOperators[i]=(Perturbation) Class.forName("Perturbation."+config.getPerturbation()[i]).
				getConstructor(Instance.class,Config.class,HashMap.class,IntraLocalSearch.class).
				newInstance(instance,config,omegaSetup,intraLocalSearch);
			}

		} catch (InstantiationException | IllegalAccessException | IllegalArgumentException
				| InvocationTargetException | NoSuchMethodException | SecurityException
				| ClassNotFoundException e) {
			e.printStackTrace();
		}

	}

	public void search()
	{
		iterator=0;
//		first=System.currentTimeMillis();
		first=(long) (this.startTime * 1000);

        referenceSolution.numRoutes = instance.getMinNumberRoutes();
        constructSolution.construct(referenceSolution);

        feasibilityOperator.makeFeasible(referenceSolution);
        localSearch.localSearch(referenceSolution, true);

        Map<String, Object> best = SQLiteHelper.loadBest(this.sharedDB);
        if (best != null) {
            initSolutionList = (List<Integer>) best.get("solution");
            referenceSolution.loadInitSolution(initSolutionList);
        }
        bestSolution.clone(referenceSolution);
        bestF = bestSolution.f;
		while(!stoppingCriterion())
		{
			iterator++;

			solution.clone(referenceSolution);

			selectedPerturbation=pertubOperators[rand.nextInt(pertubOperators.length)];
			selectedPerturbation.applyPerturbation(solution);
			feasibilityOperator.makeFeasible(solution);
			localSearch.localSearch(solution,true);
			distanceLS=pairwiseDistance.pairwiseSolutionDistance(solution,referenceSolution);
			evaluateSolution();
			distAdjustment.distAdjustment();

			selectedPerturbation.getChosenOmega().setDistance(distanceLS);//update

			if(acceptanceCriterion.acceptSolution(solution))
				referenceSolution.clone(solution);
		}

		totalTime=(double)(System.currentTimeMillis()-first)/1000;
	}

	public void evaluateSolution()
	{
        if((solution.f-bestF)<-epsilon) {
            bestF = solution.f;

            bestSolution.clone(solution);
            iteratorMF = iterator;
            timeAF = (double) (System.currentTimeMillis() - first) / 1000;

            if (print) {
                System.out.println("solution quality: " + bestF
                        + " gap: " + deci.format(getGap()) + "%"
                        + " K: " + solution.numRoutes
                        + " iteration: " + iterator
                        + " eta: " + deci.format(acceptanceCriterion.getEta())
                        + " omega: " + deci.format(selectedPerturbation.omega)
                        + " time: " + timeAF
                );
                // .db output
                if (Instant.now().getEpochSecond() - preUpdate.getEpochSecond() > this.updateInterval) {
                    SQLiteHelper.saveBest(this.sharedDB, timeAF, bestF, bestSolution.toListString(), "ails2");
                    this.preUpdate = Instant.now();
                }
            }
        }
	}

	private boolean stoppingCriterion()
	{
		switch(stoppingCriterionType)
		{
			case Iteration: 	if(bestF<=optimal||executionMaximumLimit<=iterator)
									return true;
								break;

			case Time: 	if(bestF<=optimal||executionMaximumLimit<(System.currentTimeMillis()-first)/1000)
							return true;
						break;
		}
		return false;
	}

//	public static void main(String[] args)
//	{
//        // get size
////        String instance_name = args[1];
////        Matcher m = Pattern.compile("[+-]?\\d+").matcher(instance_name);
////        Integer size = m.find() ? Integer.parseInt(m.group()) : null;
////        System.out.println("size: "+size);
//
//
//        for (String s: args){
//            System.out.println(s);
//        }
//
//        String root_path = "data/cvrplib_1019_subset/";
//        File dir = new File(root_path);
//        File[] files = dir.listFiles();
//
//        for (File f : files) {
//            String instance_name = "";
//            if (!f.isDirectory()){
//                if (FilenameUtils.isExtension(f.getName(), "vrp")){
//                    instance_name = f.getName();
//                }
//                else continue;
//                System.out.println(instance_name);
//            }
//            else continue;
//            List<Integer> nums = new ArrayList<>();
//            Matcher m = Pattern.compile("[+-]?\\d+").matcher(instance_name);
//            while (m.find()) {
//                nums.add(Integer.parseInt(m.group()));
//            }
//            Integer size = nums.get(0);
//            Integer capacity = nums.get(1);
//            System.out.printf("size: %d\tcapacity: %d\n", size, capacity);
//
//            InputParameters reader=new InputParameters();
//            String[] crt_args = {
//                    "-file", root_path+instance_name,
//                    "-rounded", "true",
//                    "-best", "0",
//                    "-limit", Integer.toString((int) Math.ceil(60*size/25)),
////                    "-limit", "10",
//                    "-stoppingCriterion", "Time",
////                    "-dMax", Integer.toString((int) Math.ceil(0.03 * size)),
////                    "-dMin", Integer.toString((int) Math.ceil(0.01 * size)),
////                    "-gamma", Integer.toString((int) Math.ceil(0.03 * size)),
////                    "-varphi", Integer.toString((int) Math.ceil(0.04 * size)),
//
//                    "-dMax", Integer.toString((int) Math.ceil(0.04 * size)),
//                    "-dMin", Integer.toString((int) Math.ceil(0.013 * size)),
//                    "-gamma", Integer.toString((int) Math.ceil(1.5 * Math.sqrt(size))),
//                    "-varphi", Integer.toString((int) Math.ceil(0.05 * size)),
//
////                    "-dMax", Integer.toString((int) Math.ceil(1.5 * size / capacity)),
////                    "-dMin", Integer.toString((int) Math.ceil(0.5 * size / capacity)),
////                    "-gamma", Integer.toString((int) Math.ceil(1.5 * size / capacity)),
////                    "-varphi", Integer.toString((int) Math.ceil(2. * size / capacity)),
//            };
//            reader.readingInput(crt_args);
//            Instance instance=new Instance(reader);
//
//            AILSII ailsII=new AILSII(instance,reader);
//
//            ailsII.search();
//        }
//	}

    public static void main(String[] args){

        InputParameters reader=new InputParameters();
        reader.readingInput(args);

        Instance instance=new Instance(reader);

        AILSII ailsII=new AILSII(instance,reader);

        ailsII.search();
    }

	public Solution getBestSolution() {
		return bestSolution;
	}

	public double getBestF() {
		return bestF;
	}

	public double getGap()
	{
		return 100*((bestF-optimal)/optimal);
	}

	public boolean isPrint() {
		return print;
	}

	public void setPrint(boolean print) {
		this.print = print;
	}

	public Solution getSolution() {
		return solution;
	}

	public int getIterator() {
		return iterator;
	}

	public String printOmegas()
	{
		String str="";
		for (int i = 0; i < pertubOperators.length; i++)
		{
			str+="\n"+omegaSetup.get(this.pertubOperators[i].perturbationType+""+referenceSolution.numRoutes);
		}
		return str;
	}

	public Perturbation[] getPertubOperators() {
		return pertubOperators;
	}

	public double getTotalTime() {
		return totalTime;
	}

	public double getTimePerIteration()
	{
		return totalTime/iterator;
	}

	public double getTimeAF() {
		return timeAF;
	}

	public int getIteratorMF() {
		return iteratorMF;
	}

	public double getConvergenceIteration()
	{
		return (double)iteratorMF/iterator;
	}

	public double convergenceTime()
	{
		return (double)timeAF/totalTime;
	}

}
