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

        // 初始化输出目录
        // initializeOutputDirectory(); // 放到设置目录后再调用
    }

    // ================ [新增] 设置自定义输出目录 ================
    public void setOutputDirectory(String path) {
        if (path != null && !path.isEmpty()) {
            this.outputDirectory = path;
            // 确保路径以分隔符结尾
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

        // 如果只输出最终解，我们通常不希望文件名带时间戳，而是固定的 instanceName.sol 以便脚本查找
        // 但这里为了兼容原有逻辑，可以保留。
        // 建议：如果是最终解(totalTime调用)，使用 instanceName.sol 覆盖可能更好，或者保持原样。
        // 这里保持原样逻辑，但在 writeFinalSolutionToFile 可能会希望覆盖。

        // 如果想让最终结果文件名固定为 output_dir/instance_name.sol (方便run.py收集)，可以使用：
        // return instanceName + ".sol";

        // 保持原逻辑：
        if (!name.toLowerCase().endsWith(".sol")) {
            name = name + ".sol";
        }
        return name;
    }

    // [新增] 获取固定的文件名，方便外部脚本读取
    private String getFixedFilename() {
         String name = (instanceName == null || instanceName.trim().isEmpty()) ? "instance" : instanceName.trim();
         if (!name.toLowerCase().endsWith(".sol")) {
            name = name + ".sol";
        }
        return name;
    }

    private void writeSolutionToFile(double currentBestF, double currentTime) {
        // String filename = generateSafeFilename(currentTime);
        // 为了配合 run.py 收集结果，建议使用固定文件名覆盖，或者追加模式。
        // 这里为了安全，我们使用固定文件名覆盖模式 (最新解覆盖旧解)，
        // 或者如果需要保存历史，可以维持原样。
        // 考虑到 run.py 通常只看最终结果，这里我们修改为覆盖写同一个文件：

        String filename = getFixedFilename();
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath, false)) { // false = overwrite
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
        // 使用固定文件名，确保 run.py 能找到
        String filename = getFixedFilename();
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath, false)) {
            for (int i = 0; i < bestSolution.numRoutes; i++) {
                String routeNodes = getRouteNodes(i);
                writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
            }
            writer.write("Cost " + deci.format(bestF).replace(",", "."));
            writer.flush();
            if (print) {
                System.out.println("Final solution saved to: " + fullPath);
                // System.out.println("Final solution cost: " + deci.format(bestF).replace(",", "."));
            }
        } catch (IOException e) {
            System.err.println("写入最终解决方案文件失败: " + e.getMessage());
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
            // 即使不输出所有，初始化时也写一次，确保有文件存在
            double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
            writeSolutionToFile(bestF, initialTime);
        }

        while (!stoppingCriterion()) {
            iterator++;
            solution.clone(referenceSolution);
            pertubOperators[0].applyPerturbation(solution);
            feasibilityOperator.makeFeasible(solution);
            localSearch.localSearch(solution, true);
            distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolution);
            evaluateSolution();
            distAdjustment.distAdjustment();
            pertubOperators[0].getChosenOmega().setDistance(distanceLS);
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

                // 总是更新最新的解文件，这样被杀进程时也有最新结果
                writeSolutionToFile(bestF, timeAF);
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

        // [修改] 仅当没有手动设置输出目录时，才使用默认结构
        if (!customOutputSet) {
            this.outputDirectory = "Results/" + instanceName + "/";
        }

        initializeOutputDirectory();
        initializeCSVFile();
        // System.out.println("输出目录设置为: " + this.outputDirectory);
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        Instance instance = new Instance(reader);
        AILSII ailsII = new AILSII(instance, reader);

        String instanceName = "default";
        String customOutput = null;

        // [修改] 解析命令行参数，查找 -output
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
            // [新增]
            if (args[i].equals("-output") && i + 1 < args.length) {
                customOutput = args[i + 1];
            }
        }

        // [新增] 优先设置 output 目录
        if (customOutput != null) {
            ailsII.setOutputDirectory(customOutput);
        }

        // 设置实例名 (setInstanceName 内部会检查 customOutputSet)
        ailsII.setInstanceName(instanceName);

        boolean outputAllSteps = false;
        ailsII.setOutputAllSolutions(outputAllSteps);

        if (customOutput != null) {
            System.out.println("搜索开始: " + instanceName + " (Output: " + customOutput + ")");
        } else {
            System.out.println("搜索开始: " + instanceName);
        }

        ailsII.search();
    }

    // ... (其余 Getters/Setters 保持不变，此处省略以节省空间) ...
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