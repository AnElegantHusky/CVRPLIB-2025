/**
 * Copyright 2022, Vinícius R. Máximo
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

    // ================ 文件输出相关变量 ================
    private String outputDirectory = "Results/"; // 设置输出目录
    private boolean outputAllSolutions = false; // 控制是否输出所有解，默认为false（只输出最终解）
    private String instanceName = "default"; // 存储实例名称
    private FileWriter csvWriter; // CSV文件写入器
    private Config config; // 存储Config

    public AILSII(Instance instance,InputParameters reader)
    {
        this.instance=instance;
        Config config=reader.getConfig();

        this.config = config;
        // 移除了 ExecutorService 的初始化

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

        // 初始化输出目录
        initializeOutputDirectory();
    }

    // ================ 文件输出辅助方法 ================
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

    private void initializeCSVFile() {
        try {
            String csvFilePath = outputDirectory + instanceName + ".csv";
            csvWriter = new FileWriter(csvFilePath);
            System.out.println("CSV文件已创建: " + csvFilePath);
        } catch (IOException e) {
            System.err.println("创建CSV文件失败: " + e.getMessage());
        }
    }

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

    private String getRouteNodes(int routeIndex) {
        String routeString = bestSolution.routes[routeIndex].toString2();
        int colonIndex = routeString.indexOf(":");
        if (colonIndex != -1 && colonIndex + 1 < routeString.length()) {
            return routeString.substring(colonIndex + 1).trim();
        }
        return routeString.trim();
    }

    private String generateSafeFilename(double time) {
        String name = (instanceName == null || instanceName.trim().isEmpty()) ? "instance" : instanceName.trim();
        name = name.replaceAll("[\\\\/:*?\"<>|]", "_");
        if (!name.toLowerCase().endsWith(".sol")) {
            name = name + ".sol";
        }
        return name;
    }

    private void writeSolutionToFile(double currentBestF, double currentTime) {
        String filename = generateSafeFilename(currentTime);
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath)) {
            for (int i = 0; i < bestSolution.numRoutes; i++) {
                String routeNodes = getRouteNodes(i);
                writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
            }
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

    private void writeFinalSolutionToFile() {
        String filename = generateSafeFilename(totalTime);
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath)) {
            for (int i = 0; i < bestSolution.numRoutes; i++) {
                String routeNodes = getRouteNodes(i);
                writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
            }
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

    public void search() {
        iterator = 0;
        first = threadMXBean.getCurrentThreadCpuTime(); // 获取当前线程的CPU时间

        referenceSolution.numRoutes = instance.getMinNumberRoutes();
        constructSolution.construct(referenceSolution);

        feasibilityOperator.makeFeasible(referenceSolution);
        localSearch.localSearch(referenceSolution, true);

        // 初始化最优解
        bestSolution.clone(referenceSolution);
        bestF = bestSolution.f;

        // 如果配置为输出所有解，则保存初始解
        if (outputAllSolutions) {
            double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
            if (print) {
                System.out.println("Initial solution: " + initialTime + ";" + bestF);
            }
            writeSolutionToFile(bestF, initialTime);
        }

        while (!stoppingCriterion()) {
            iterator++;

            // ================ 修改：移除线程并行，固定使用第一种扰动 ================

            // 1. 基于参考解克隆出当前工作解
            solution.clone(referenceSolution);

            // 2. 固定选择一个扰动算子 (pertubOperators[0])
            pertubOperators[0].applyPerturbation(solution);

            // 3. 恢复可行性
            feasibilityOperator.makeFeasible(solution);

            // 4. 局部搜索
            localSearch.localSearch(solution, true);

            // 5. 计算距离和接受准则 (保持原有逻辑)
            distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolution);

            evaluateSolution(); // 评估是否为全局最优

            distAdjustment.distAdjustment();
            pertubOperators[0].getChosenOmega().setDistance(distanceLS);

            if (acceptanceCriterion.acceptSolution(solution)) {
                referenceSolution.clone(solution);
            }

            // ================ 修改结束 ================
        }

        // 计算总时间 (仅计算当前主线程时间)
        long totalCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
        totalTime = (double) totalCpuTime / 1_000_000_000.0; // 转换为秒

        // 保存最终的最优解（使用总时间作为文件名）
        writeFinalSolutionToFile();

        // 关闭CSV文件
        closeCSVFile();
    }

    public void evaluateSolution() {
        if ((solution.f - bestF) < -epsilon) {
            if (solution != null && solution.routes != null) {
                bestF = solution.f;
                bestSolution.clone(solution);
                iteratorMF = iterator;

                // ================ 修改：仅使用主线程 CPU 时间 ================
                long totalCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
                timeAF = (double) totalCpuTime / 1_000_000_000.0;
                // ================ 修改结束 ================

                if (print) {
                    System.out.println(timeAF + ";" + bestF);
                }

                // 写入CSV文件
                writeToCSV(timeAF, bestF);

                // 如果配置为输出所有解，则每次找到更好的解时都保存文件
                if (outputAllSolutions) {
                    writeSolutionToFile(bestF, timeAF);
                }
            }
        }
    }

    private boolean stoppingCriterion() {
        switch (stoppingCriterionType) {
            case Iteration:
                if (bestF <= optimal || executionMaximumLimit <= iterator)
                    return true;
                break;

            case Time:
                // ================ 修改：仅使用主线程 CPU 时间 ================
                double elapsedCpuSeconds = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000.0;

                if (bestF <= optimal || executionMaximumLimit < elapsedCpuSeconds)
                    return true;
                // ================ 修改结束 ================
                break;
        }
        return false;
    }

    public void setInstanceName(String instanceName) {
        this.outputDirectory = "Results/" + instanceName + "/";
        this.instanceName = instanceName;
        initializeOutputDirectory();
        initializeCSVFile();
        System.out.println("输出目录设置为: " + this.outputDirectory);
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        Instance instance = new Instance(reader);

        AILSII ailsII = new AILSII(instance, reader);

        String instanceName = "default";
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

        ailsII.setInstanceName(instanceName);

        boolean outputAllSteps = false;
        ailsII.setOutputAllSolutions(outputAllSteps);

        if (outputAllSteps) {
            System.out.println("输出模式: 每一步都输出解文件 - 实例: " + instanceName);
        } else {
            System.out.println("输出模式: 只输出最终解 - 实例: " + instanceName);
        }

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

    public boolean isOutputAllSolutions() {
        return outputAllSolutions;
    }

    public void setOutputAllSolutions(boolean outputAllSolutions) {
        this.outputAllSolutions = outputAllSolutions;
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