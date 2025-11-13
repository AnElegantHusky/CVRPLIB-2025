/**
 * 	Copyright 2022, Vinícius R. Máximo
 *	Distributed under the terms of the MIT License. 
 *	SPDX-License-Identifier: MIT
 */
package SearchMethod;

import java.lang.reflect.InvocationTargetException;
import java.text.DecimalFormat;
import java.util.HashMap;
import java.util.Random;

import Auxiliary.Distance;
import Auxiliary.CpuTime;
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
	
	Instance instance;
	Config config;
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
	
	public AILSII(Instance instance,InputParameters reader)
	{ 
		this.instance=instance;
		this.config=reader.getConfig();
		this.optimal=reader.getBest();
		this.executionMaximumLimit=reader.getTimeLimit();
		
		this.epsilon=this.config.getEpsilon();
		this.stoppingCriterionType=this.config.getStoppingCriterionType();
		this.idealDist=new IdealDist();
		this.solution =new Solution(instance,this.config);
		this.referenceSolution =new Solution(instance,this.config);
		this.bestSolution =new Solution(instance,this.config);
		this.numIterUpdate=this.config.getGamma();
		
		this.pairwiseDistance=new Distance();
		
		this.pertubOperators=new Perturbation[this.config.getPerturbation().length];
		
		this.distAdjustment=new DistAdjustment( idealDist, this.config, executionMaximumLimit);
		
		this.intraLocalSearch=new IntraLocalSearch(instance,this.config);
		
		this.localSearch=new LocalSearch(instance,this.config,intraLocalSearch);
		
		this.feasibilityOperator=new FeasibilityPhase(instance,this.config,intraLocalSearch);
		
		this.constructSolution=new ConstructSolution(instance,this.config);
		
		OmegaAdjustment newOmegaAdjustment;
		for (int i = 0; i < this.config.getPerturbation().length; i++) 
		{
			newOmegaAdjustment=new OmegaAdjustment(this.config.getPerturbation()[i], this.config,instance.getSize(),idealDist);
			omegaSetup.put(this.config.getPerturbation()[i]+"", newOmegaAdjustment);
		}
		
		this.acceptanceCriterion=new AcceptanceCriterion(instance,this.config,executionMaximumLimit);

		try 
		{
			for (int i = 0; i < pertubOperators.length; i++) 
			{
				this.pertubOperators[i]=(Perturbation) Class.forName("Perturbation."+this.config.getPerturbation()[i]).
				getConstructor(Instance.class,Config.class,HashMap.class,IntraLocalSearch.class).
				newInstance(instance,this.config,omegaSetup,intraLocalSearch);
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
		first=CpuTime.getCpuTimeMillis();
		referenceSolution.numRoutes=instance.getMinNumberRoutes();
		constructSolution.construct(referenceSolution);

		feasibilityOperator.makeFeasible(referenceSolution);
		localSearch.localSearch(referenceSolution,true);
		bestSolution.clone(referenceSolution);
		
		while(!stoppingCriterion())
		{
			iterator++;

            solution.clone(referenceSolution);

            // 频率与开关：每 stagnationThreshold 迭代触发一次分解，且强制接受
            boolean decoNow = config.isDecoEnabled() && config.getStagnationThreshold() > 0 
                && (iterator % config.getStagnationThreshold() == 0);

            if (decoNow) {
                // 选择 Decomposition 算子
				selectedPerturbation = pertubOperators[2];
            } else {
                // 从非分解算子中随机选择 deco:2, others:0 and 1
				selectedPerturbation = pertubOperators[rand.nextInt(pertubOperators.length - 1)];
            }

            selectedPerturbation.applyPerturbation(solution);
			feasibilityOperator.makeFeasible(solution);
			localSearch.localSearch(solution,true);

			distanceLS=pairwiseDistance.pairwiseSolutionDistance(solution,referenceSolution);
			
			evaluateSolution();
			distAdjustment.distAdjustment();
			
			if(selectedPerturbation.getChosenOmega() != null)
				selectedPerturbation.getChosenOmega().setDistance(distanceLS);//update
			
            if (decoNow) {
                // 分解触发时强制接受
                referenceSolution.clone(solution);
            } else {
                if(acceptanceCriterion.acceptSolution(solution))
                    referenceSolution.clone(solution);
            }
		}
		
		totalTime=CpuTime.getCpuTimeSeconds() - (first / 1000.0);
	}
	
	public void evaluateSolution()
	{
		if((solution.f-bestF)<-epsilon)
		{		
			bestF=solution.f;
			
			bestSolution.clone(solution);
			iteratorMF=iterator;
			timeAF=CpuTime.getCpuTimeSeconds() - (first / 1000.0);
				
			if(print)
			{
				System.out.println(String.format("%.3f;%.1f", timeAF, bestF));
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
							
			case Time: 	if(bestF<=optimal||executionMaximumLimit<(CpuTime.getCpuTimeSeconds() - (first / 1000.0)))
							return true;
						break;
		}
		return false;
	}
	
	public static void main(String[] args) 
	{
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
