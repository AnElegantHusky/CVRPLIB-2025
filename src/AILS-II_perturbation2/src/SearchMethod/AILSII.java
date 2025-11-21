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
    private String outputDirectory = "Results/"; // 默认输出目录
    private boolean customOutputSet = false;     // [新增] 标记是否使用了自定义输出目录
    private boolean outputAllSolutions = false;
    private String instanceName = "default";
    private FileWriter csvWriter;
    private Config config;

    public AILSII(Instance instance,InputParameters reader)
    {
        this.instance=instance;
        Config config=reader.getConfig();

        this.config = config;

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

        // 初始化输出目录 (推迟到参数设置后)
        // initializeOutputDirectory();
    }

    // ================ [新增] 设置输出目录的方法 ================
    public void setOutputDirectory(String path) {
        if (path != null && !path.isEmpty()) {
            this.outputDirectory = path;
            if (!this.outputDirectory.endsWith(File.separator)) {
                this.outputDirectory += File.separator;
            }
            this.customOutputSet = true;
            initializeOutputDirectory();
        }
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
            // System.out.println("CSV文件已创建: " + csvFilePath);
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
                // System.out.println("CSV文件已关闭");
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

        // 为了方便外部脚本读取，建议使用固定文件名 (instanceName.sol)，覆盖写入
        // 如果这里想保留带时间戳的文件，可以保留原逻辑，但下面为了配合run.py，我使用了固定文件名逻辑。
        if (!name.toLowerCase().endsWith(".sol")) {
            name = name + ".sol";
        }
        return name;
    }

    // [新增] 获取固定的文件名，不带时间戳
    private String getFixedFilename() {
         String name = (instanceName == null || instanceName.trim().isEmpty()) ? "instance" : instanceName.trim();
         if (!name.toLowerCase().endsWith(".sol")) {
            name = name + ".sol";
        }
        return name;
    }

    private void writeSolutionToFile(double currentBestF, double currentTime) {
        // 使用固定文件名覆盖写入，确保最新的解总是在 instanceName.sol 中
        String filename = getFixedFilename();
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath, false)) { // false = 覆盖模式
            for (int i = 0; i < bestSolution.numRoutes; i++) {
                String routeNodes = getRouteNodes(i);
                writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
            }
            writer.write("Cost " + deci.format(currentBestF).replace(",", ".") + "\n");
            writer.write("Time " + deci.format(currentTime).replace(",", "."));
            writer.flush();
            if (print) {
                // System.out.println("Solution saved to: " + fullPath);
            }
        } catch (IOException e) {
            System.err.println("写入解决方案文件失败: " + e.getMessage());
        } catch (Exception e) {
            System.err.println("写入文件时发生错误: " + e.getMessage());
        }
    }

    private void writeFinalSolutionToFile() {
        // 逻辑同上，确保最终结果也被写入同一个文件
        writeSolutionToFile(bestF, totalTime);
        if (print) {
             String fullPath = outputDirectory + getFixedFilename();
             System.out.println("Final solution saved to: " + fullPath);
        }
    }

    public void search() {
        iterator = 0;
        first = threadMXBean.getCurrentThreadCpuTime();

        referenceSolution.numRoutes = instance.getMinNumberRoutes();
        constructSolution.construct(referenceSolution);

        feasibilityOperator.makeFeasible(referenceSolution);
        localSearch.localSearch(referenceSolution, true);

        bestSolution.clone(referenceSolution);
        bestF = bestSolution.f;

        if (outputAllSolutions) {
            double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
            if (print) {
                System.out.println("Initial solution: " + initialTime + ";" + bestF);
            }
            writeSolutionToFile(bestF, initialTime);
        } else {
            // 即使不输出所有步骤，初始化时也写一次，占位
            double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
            writeSolutionToFile(bestF, initialTime);
        }

        while (!stoppingCriterion()) {
            iterator++;
            solution.clone(referenceSolution);
            // 注意：原代码这里使用的是 pertubOperators[1]，为了通用性，我保留您的逻辑
            pertubOperators[1].applyPerturbation(solution);
            feasibilityOperator.makeFeasible(solution);
            localSearch.localSearch(solution, true);
            distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolution);
            evaluateSolution();
            distAdjustment.distAdjustment();
            pertubOperators[1].getChosenOmega().setDistance(distanceLS);

            if (acceptanceCriterion.acceptSolution(solution)) {
                referenceSolution.clone(solution);
            }
        }

        long totalCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
        totalTime = (double) totalCpuTime / 1_000_000_000.0;

        writeFinalSolutionToFile();
        closeCSVFile();
    }

    public void evaluateSolution() {
        if ((solution.f - bestF) < -epsilon) {
            if (solution != null && solution.routes != null) {
                bestF = solution.f;
                bestSolution.clone(solution);
                iteratorMF = iterator;

                long totalCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
                timeAF = (double) totalCpuTime / 1_000_000_000.0;

                if (print) {
                    System.out.println(timeAF + ";" + bestF);
                }

                writeToCSV(timeAF, bestF);

                if (outputAllSolutions) {
                    writeSolutionToFile(bestF, timeAF);
                } else {
                    // 即使不输出所有历史，也建议实时更新最优解文件
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
                double elapsedCpuSeconds = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000.0;
                if (bestF <= optimal || executionMaximumLimit < elapsedCpuSeconds)
                    return true;
                break;
        }
        return false;
    }

    public void setInstanceName(String instanceName) {
        this.instanceName = instanceName;

        // [修改] 仅当没有手动设置输出目录时，才使用默认的 Results/InstanceName 结构
        if (!customOutputSet) {
            this.outputDirectory = "Results/" + instanceName + "/";
        }

        initializeOutputDirectory();
        initializeCSVFile();
        System.out.println("输出目录: " + this.outputDirectory);
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        Instance instance = new Instance(reader);
        AILSII ailsII = new AILSII(instance, reader);

        String instanceName = "default";
        String customOutput = null; // [新增]

        // 解析命令行参数
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
            }
            // [新增] 解析 -output
            if (args[i].equals("-output") && i + 1 < args.length) {
                customOutput = args[i + 1];
            }
        }

        // [新增] 优先设置 output 参数
        if (customOutput != null) {
            ailsII.setOutputDirectory(customOutput);
        }

        // 设置实例名 (setInstanceName 会检查 customOutputSet)
        ailsII.setInstanceName(instanceName);

        boolean outputAllSteps = false;
        ailsII.setOutputAllSolutions(outputAllSteps);

        if (customOutput != null) {
             System.out.println("输出模式: 指定目录输出 - " + customOutput);
        } else {
             System.out.println("输出模式: 默认目录结构 - Results/" + instanceName);
        }

        ailsII.search();
    }

    // Getters/Setters 省略部分保持不变...
    public Solution getBestSolution() { return bestSolution; }
    public double getBestF() { return bestF; }
    public double getGap() { return 100*((bestF-optimal)/optimal); }
    public boolean isPrint() { return print; }
    public void setPrint(boolean print) { this.print = print; }
    public boolean isOutputAllSolutions() { return outputAllSolutions; }
    public void setOutputAllSolutions(boolean outputAllSolutions) { this.outputAllSolutions = outputAllSolutions; }
    public Solution getSolution() { return solution; }
    public int getIterator() { return iterator; }
    public String printOmegas() { return ""; }
    public Perturbation[] getPertubOperators() { return pertubOperators; }
    public double getTotalTime() { return totalTime; }
    public double getTimePerIteration() { return totalTime/iterator; }
    public double getTimeAF() { return timeAF; }
    public int getIteratorMF() { return iteratorMF; }
    public double getConvergenceIteration() { return (double)iteratorMF/iterator; }
    public double convergenceTime() { return (double)timeAF/totalTime; }
}