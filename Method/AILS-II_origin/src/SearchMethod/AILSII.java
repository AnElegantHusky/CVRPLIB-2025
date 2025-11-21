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
import java.io.FileWriter;
import java.io.IOException;
import java.io.File;

import Auxiliary.Distance;
import Data.Instance;
import DiversityControl.DistAdjustment;
import DiversityControl.OmegaAdjustment;
import DiversityControl.AcceptanceCriterion;
import DiversityControl.IdealDist;
import Improvement.LocalSearch;
import Improvement.IntraLocalSearch;
import Improvement.FeasibilityPhase;
import Perturbation.Perturbation;
import Perturbation.InsertionHeuristic;
import Solution.Solution;
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;


public class AILSII 
{
	//----------Problema------------
	Solution solution,referenceSolution,bestSolution;
	
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
	ThreadMXBean threadMXBean;
	
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
	
	// ================ 修改开始：添加文件输出功能 ================
	//----------文件输出------------
	private String outputDirectory = "Results/"; // 设置输出目录
	private boolean outputAllSolutions = false; // 控制是否输出所有解，默认为false（只输出最终解）
	private String instanceName = "default"; // 存储实例名称
	private FileWriter csvWriter; // CSV文件写入器
	// ================ 修改结束 ================

	public AILSII(Instance instance,InputParameters reader)
	{ 
		this.instance=instance;
		Config config=reader.getConfig();
		this.optimal=reader.getBest();
		this.executionMaximumLimit=reader.getTimeLimit();
		this.threadMXBean = ManagementFactory.getThreadMXBean();
		
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
		
		// ================ 修改开始：初始化输出目录 ================
		// 初始化输出目录
		initializeOutputDirectory();
		// ================ 修改结束 ================
		
	}

	// ================ 修改开始：添加新方法 ================
	/**
	 * 初始化输出目录
	 */
	private void initializeOutputDirectory() {
		try {
			java.io.File directory = new java.io.File(outputDirectory);
			if (!directory.exists()) {
				directory.mkdirs();
			}
		} catch (Exception e) {
			System.err.println("创建输出目录失败: " + e.getMessage());
		}
	}

	/**
	 * 初始化CSV文件
	 */
	private void initializeCSVFile() {
		try {
			String csvFilePath = outputDirectory + instanceName + ".csv";
			csvWriter = new FileWriter(csvFilePath);
			System.out.println("CSV文件已创建: " + csvFilePath);
		} catch (IOException e) {
			System.err.println("创建CSV文件失败: " + e.getMessage());
		}
	}

	/**
	 * 写入CSV数据
	 * @param time 时间
	 * @param bestF 最优成本
	 */
	private void writeToCSV(double time, double bestF) {
		if (csvWriter != null) {
			try {
				csvWriter.write(deci.format(time).replace(",", ".") + ";" + deci.format(bestF).replace(",", ".") + "\n");
				csvWriter.flush();
			} catch (IOException e) {
				System.err.println("写入CSV文件失败: " + e.getMessage());
			}
		}
	}

	/**
	 * 关闭CSV文件
	 */
	private void closeCSVFile() {
		if (csvWriter != null) {
			try {
				csvWriter.close();
				System.out.println("CSV文件已关闭");
			} catch (IOException e) {
				System.err.println("关闭CSV文件失败: " + e.getMessage());
			}
		}
	}

	/**
	 * 获取指定路线的节点序列
	 * @param routeIndex 路线索引
	 * @return 节点序列字符串
	 */
	private String getRouteNodes(int routeIndex) {
		// 使用 Route 类的 toString2() 方法获取路线信息
		String routeString = bestSolution.routes[routeIndex].toString2();
		
		// 去掉开头的 "Route #X: " 部分，只保留节点序列
		int colonIndex = routeString.indexOf(":");
		if (colonIndex != -1 && colonIndex + 1 < routeString.length()) {
			return routeString.substring(colonIndex + 1).trim();
		}
		return routeString.trim();
	}

	/**
	 * 生成安全的文件名（只使用时间）
	 * @param time 时间
	 * @return 安全的文件名
	 */
	private String generateSafeFilename(double time) {
		String timeStr = deci.format(time).replace(",", ".");
		
		// 移除文件名中的非法字符
		timeStr = timeStr.replaceAll("[\\\\/:*?\"<>|]", "_");
		
		return timeStr + ".sol";
	}

	/**
	 * 将解决方案写入文件
	 * @param currentBestF 当前最优成本
	 * @param currentTime 当前时间
	 */
	private void writeSolutionToFile(double currentBestF, double currentTime) {
		String filename = generateSafeFilename(currentTime);
		String fullPath = outputDirectory + filename;
		
		try (FileWriter writer = new FileWriter(fullPath)) {
			// 写入标准的CVRP sol格式
			// 先写所有路线
			for (int i = 0; i < bestSolution.numRoutes; i++) {
				String routeNodes = getRouteNodes(i);
				writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
			}
			
			// 最后写入成本和时间
			writer.write("Cost " + deci.format(currentBestF).replace(",", ".") + "\n");
			writer.write("Time " + deci.format(currentTime).replace(",", "."));
			
			writer.flush();
			if (print) {
				System.out.println("Solution saved to: " + fullPath);
			}
		} catch (IOException e) {
			System.err.println("写入解决方案文件失败: " + e.getMessage());
		} catch (Exception e) {
			System.err.println("写入文件时发生错误: " + e.getMessage());
		}
	}

	/**
	 * 将最终解决方案写入文件（使用最终时间作为名称）
	 */
	private void writeFinalSolutionToFile() {
		// 使用最终时间作为文件名
		String formattedTime = deci.format(totalTime).replace(",", ".");
		String safeTime = formattedTime.replaceAll("[\\\\/:*?\"<>|]", "_");
		String filename = outputDirectory + safeTime + ".sol";
		
		try (FileWriter writer = new FileWriter(filename)) {
			// 写入标准的CVRP sol格式
			// 先写所有路线
			for (int i = 0; i < bestSolution.numRoutes; i++) {
				String routeNodes = getRouteNodes(i);
				writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
			}
			
			// 最后写入成本
			writer.write("Cost " + deci.format(bestF).replace(",", "."));
			
			writer.flush();
			if (print) {
				System.out.println("Final solution saved to: " + filename);
				System.out.println("Final solution cost: " + deci.format(bestF).replace(",", "."));
			}
		} catch (IOException e) {
			System.err.println("写入最终解决方案文件失败: " + e.getMessage());
		}
	}
	// ================ 修改结束 ================

	public void search() {
		iterator = 0;
		first = threadMXBean.getCurrentThreadCpuTime(); // 获取当前线程的CPU时间
		referenceSolution.numRoutes = instance.getMinNumberRoutes();
		constructSolution.construct(referenceSolution);

		feasibilityOperator.makeFeasible(referenceSolution);
		localSearch.localSearch(referenceSolution, true);
		
		// ================ 修改开始：修复初始化问题 ================
		// 先设置bestSolution
		bestSolution.clone(referenceSolution);
		bestF = bestSolution.f; // 使用实际的解成本，而不是Double.MAX_VALUE
		
		// ================ 修改开始：根据配置决定是否保存初始解 ================
		// 如果配置为输出所有解，则保存初始解
		if (outputAllSolutions) {
			double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
			if (print) {
				System.out.println("Initial solution: " + initialTime + ";" + bestF);
			}
			writeSolutionToFile(bestF, initialTime);
		}
		// ================ 修改结束 ================
		
		while (!stoppingCriterion()) {
			iterator++;

			solution.clone(referenceSolution);

			selectedPerturbation = pertubOperators[rand.nextInt(pertubOperators.length)];
			selectedPerturbation.applyPerturbation(solution);
			feasibilityOperator.makeFeasible(solution);
			localSearch.localSearch(solution, true);
			distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolution);

			evaluateSolution();
			distAdjustment.distAdjustment();

			selectedPerturbation.getChosenOmega().setDistance(distanceLS); // update

			if (acceptanceCriterion.acceptSolution(solution))
				referenceSolution.clone(solution);
		}

		totalTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000; // 转换为秒
		
		// ================ 修改开始：在搜索结束后保存最终解 ================
		// 保存最终的最优解（使用总时间作为文件名）
		writeFinalSolutionToFile();
		
		// 关闭CSV文件
		closeCSVFile();
		// ================ 修改结束 ================
	}

	public void evaluateSolution() {
		if ((solution.f - bestF) < -epsilon) {
			// ================ 修改开始：修复clone前的空指针问题 ================
			// 先检查solution是否有效
			if (solution != null && solution.routes != null) {
				bestF = solution.f;
				bestSolution.clone(solution);
				iteratorMF = iterator;
				timeAF = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;

				if (print) {
					System.out.println(timeAF + ";" + bestF);
				}
				
				// ================ 修改开始：写入CSV文件 ================
				// 每次找到更好的解时都写入CSV文件
				writeToCSV(timeAF, bestF);
				// ================ 修改结束 ================
				
				// ================ 修改开始：根据配置决定是否每次保存文件 ================
				// 如果配置为输出所有解，则每次找到更好的解时都保存文件
				if (outputAllSolutions) {
					writeSolutionToFile(bestF, timeAF);
				}
				// ================ 修改结束 ================
			}
			// ================ 修改结束 ================
		}
	}

	private boolean stoppingCriterion() {
		switch (stoppingCriterionType) {
			case Iteration:
				if (bestF <= optimal || executionMaximumLimit <= iterator)
					return true;
				break;

			case Time:
				if (bestF <= optimal || executionMaximumLimit < (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000)
					return true;
				break;
		}
		return false;
	}
	
	// ================ 修改开始：添加实例名称设置方法 ================
	public void setInstanceName(String instanceName) {
		// 根据实例名称更新输出目录
		this.outputDirectory = "Results/" + instanceName + "/";
		this.instanceName = instanceName;
		// 重新初始化输出目录
		initializeOutputDirectory();
		// 初始化CSV文件
		initializeCSVFile();
		System.out.println("输出目录设置为: " + this.outputDirectory);
	}
	// ================ 修改结束 ================
	
	public static void main(String[] args) 
	{
		InputParameters reader = new InputParameters();
		reader.readingInput(args);
		
		Instance instance = new Instance(reader);
		
		AILSII ailsII = new AILSII(instance, reader);
		
		// ================ 修改开始：从命令行参数获取实例名称 ================
		String instanceName = "default";
		// 尝试从命令行参数中提取实例名称
		for (int i = 0; i < args.length; i++) {
			if (args[i].equals("-file") && i + 1 < args.length) {
				String filePath = args[i + 1];
				File file = new File(filePath);
				String fileName = file.getName();
				if (fileName.lastIndexOf(".") > 0) {
					instanceName = fileName.substring(0, fileName.lastIndexOf("."));
				} else {
					instanceName = fileName;
				}
				break;
			}
		}
		
		// 设置实例名称（这会自动创建对应的输出目录）
		ailsII.setInstanceName(instanceName);
		
		// 设置输出模式
		boolean outputAllSteps = false; // 这里设置为false只输出最终解
		ailsII.setOutputAllSolutions(outputAllSteps);
		
		if (outputAllSteps) {
			System.out.println("输出模式: 每一步都输出解文件 - 实例: " + instanceName);
		} else {
			System.out.println("输出模式: 只输出最终解 - 实例: " + instanceName);
		}
		// ================ 修改结束 ================
		
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

	// ================ 修改开始：添加输出模式控制方法 ================
	public boolean isOutputAllSolutions() {
		return outputAllSolutions;
	}

	public void setOutputAllSolutions(boolean outputAllSolutions) {
		this.outputAllSolutions = outputAllSolutions;
	}
	// ================ 修改结束 ================
	
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