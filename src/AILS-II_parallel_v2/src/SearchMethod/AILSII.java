/**
 * Copyright 2022, Vinícius R. Máximo
 *	Distributed under the terms of the MIT License.
 *	SPDX-License-Identifier: MIT
 */
package SearchMethod;

import java.lang.reflect.InvocationTargetException;
import java.text.DecimalFormat;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
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
import Perturbation.PerturbationType;
import Solution.Solution;
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.Callable;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.ExecutionException;


public class AILSII
{
    // ================ 内部类：任务结果封装 ================
    private static class TaskResult {
        final Solution solution;
        final long cpuTime;
        final Perturbation perturbationUsed;

        TaskResult(Solution solution, long cpuTime, Perturbation perturbationUsed) {
            this.solution = solution;
            this.cpuTime = cpuTime;
            this.perturbationUsed = perturbationUsed;
        }
    }

    //----------核心变量------------
    int numThreads;
    Solution solution, bestSolution;

    Solution[] referenceSolutions;
    Instance[] instances;

    Perturbation[] threadPerturbations;
    FeasibilityPhase[] feasibilityOperators;
    LocalSearch[] localSearches;
    IntraLocalSearch[] intraLocalSearches;

    Perturbation[] distinctPerturbations;

    Distance pairwiseDistance;
    double bestF = Double.MAX_VALUE;
    double executionMaximumLimit;
    double optimal;

    //----------阈值与指标------------
    int numIterUpdate;
    int iterator, iteratorMF;
    long first, ini;
    double timeAF, totalTime, time;
    ThreadMXBean threadMXBean;

    private long totalWorkerCpuTime = 0L;

    Random rand = new Random(42);
    Random pertRand = new Random(42);

    HashMap<String, OmegaAdjustment> omegaSetup = new HashMap<String, OmegaAdjustment>();

    double distanceLS;

    ConstructSolution constructSolution;
    InsertionHeuristic insertionHeuristic;
    AcceptanceCriterion acceptanceCriterion;

    DistAdjustment distAdjustment;

    //---------打印与输出----------
    boolean print = true;
    IdealDist idealDist;
    double epsilon;
    DecimalFormat deci = new DecimalFormat("0.0000");
    StoppingCriterionType stoppingCriterionType;

    private String outputDirectory = "Results/";
    private boolean outputAllSolutions = false;
    private boolean customOutputSet = false; // 新增：标记是否手动设置了输出目录
    private String instanceName = "default";
    private FileWriter csvWriter;

    private ExecutorService executorService;
    private Config config;

    public AILSII(InputParameters reader, int numThreads)
    {
        this.numThreads = numThreads;
        Config config = reader.getConfig();
        this.config = config;

        this.executorService = Executors.newFixedThreadPool(numThreads);

        this.optimal = reader.getBest();
        this.executionMaximumLimit = reader.getTimeLimit();
        this.threadMXBean = ManagementFactory.getThreadMXBean();

        this.epsilon = config.getEpsilon();
        this.stoppingCriterionType = config.getStoppingCriterionType();
        this.idealDist = new IdealDist();
        this.numIterUpdate = config.getGamma();
        this.pairwiseDistance = new Distance();

        Instance mainInstance = new Instance(reader);
        this.solution = new Solution(mainInstance, config);
        this.bestSolution = new Solution(mainInstance, config);

        this.distAdjustment = new DistAdjustment(idealDist, config, executionMaximumLimit);
        this.constructSolution = new ConstructSolution(mainInstance, config);
        this.acceptanceCriterion = new AcceptanceCriterion(mainInstance, config, executionMaximumLimit);

        PerturbationType[] definedTypes = config.getPerturbation();
        this.distinctPerturbations = new Perturbation[definedTypes.length];

        for (int i = 0; i < definedTypes.length; i++)
        {
            OmegaAdjustment newOmegaAdjustment = new OmegaAdjustment(definedTypes[i], config, mainInstance.getSize(), idealDist);
            omegaSetup.put(definedTypes[i] + "", newOmegaAdjustment);
        }

        this.instances = new Instance[numThreads];
        this.referenceSolutions = new Solution[numThreads];
        this.intraLocalSearches = new IntraLocalSearch[numThreads];
        this.localSearches = new LocalSearch[numThreads];
        this.feasibilityOperators = new FeasibilityPhase[numThreads];
        this.threadPerturbations = new Perturbation[numThreads];

        for (int i = 0; i < numThreads; i++) {
            this.instances[i] = new Instance(reader);
            this.referenceSolutions[i] = new Solution(this.instances[i], config);
            this.intraLocalSearches[i] = new IntraLocalSearch(this.instances[i], config);
            this.localSearches[i] = new LocalSearch(this.instances[i], config, this.intraLocalSearches[i]);
            this.feasibilityOperators[i] = new FeasibilityPhase(this.instances[i], config, this.intraLocalSearches[i]);

            PerturbationType pType;
            if (i < definedTypes.length) {
                pType = definedTypes[i];
            } else {
                int randIndex = pertRand.nextInt(definedTypes.length);
                pType = definedTypes[randIndex];
            }

            try {
                this.threadPerturbations[i] = (Perturbation) Class.forName("Perturbation." + pType)
                        .getConstructor(Instance.class, Config.class, HashMap.class, IntraLocalSearch.class)
                        .newInstance(this.instances[i], config, omegaSetup, this.intraLocalSearches[i]);

                if (i < definedTypes.length) {
                    this.distinctPerturbations[i] = this.threadPerturbations[i];
                }

            } catch (Exception e) {
                e.printStackTrace();
                throw new RuntimeException("扰动算子初始化失败: " + pType, e);
            }
        }
        // 初始化目录放在这里，或者等 main 中设置完 InstanceName 再初始化
    }

    //----------文件输出逻辑同步------------

    // 新增：设置自定义输出目录的方法
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
        } catch (IOException e) {
            System.err.println("写入解决方案文件失败: " + e.getMessage());
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
        } catch (IOException e) {
            System.err.println("写入最终解决方案文件失败: " + e.getMessage());
        }
    }

    //----------搜索主流程------------
    public void search() {
        iterator = 0;
        first = threadMXBean.getCurrentThreadCpuTime();
        totalWorkerCpuTime = 0L;

        for (int i = 0; i < numThreads; i++) {
            referenceSolutions[i].numRoutes = instances[i].getMinNumberRoutes();
            constructSolution.construct(referenceSolutions[i]);
            feasibilityOperators[i].makeFeasible(referenceSolutions[i]);
            localSearches[i].localSearch(referenceSolutions[i], true);
        }

        bestSolution.clone(referenceSolutions[0]);
        bestF = bestSolution.f;

        for(int i = 1; i < numThreads; i++) {
            if (referenceSolutions[i].f < bestF) {
                bestSolution.clone(referenceSolutions[i]);
                bestF = referenceSolutions[i].f;
            }
        }

        double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
        if (print) {
            System.out.println("Initial solution: " + initialTime + ";" + bestF);
        }
        // 同步逻辑：初始化完成后立即输出 CSV 和 SOL (根据 outputAllSolutions)
        writeToCSV(initialTime, bestF);
        writeSolutionToFile(bestF, initialTime);

        while (!stoppingCriterion()) {
            iterator++;
            List<Callable<TaskResult>> tasks = new ArrayList<>();

            for (int i = 0; i < numThreads; i++) {
                final int threadIdx = i;
                tasks.add(() -> {
                    long taskStartTime = threadMXBean.getCurrentThreadCpuTime();
                    Solution threadSolution = new Solution(instances[threadIdx], config);
                    threadSolution.clone(referenceSolutions[threadIdx]);

                    threadPerturbations[threadIdx].applyPerturbation(threadSolution);
                    feasibilityOperators[threadIdx].makeFeasible(threadSolution);
                    localSearches[threadIdx].localSearch(threadSolution, true);

                    long taskEndTime = threadMXBean.getCurrentThreadCpuTime();
                    return new TaskResult(threadSolution, taskEndTime - taskStartTime, threadPerturbations[threadIdx]);
                });
            }

            try {
                List<Future<TaskResult>> futures = executorService.invokeAll(tasks);
                Solution bestIterSolution = null;
                Perturbation bestPerturbationUsed = null;
                double bestIterCost = Double.MAX_VALUE;
                long maxIterCpuTime = 0L;

                for (Future<TaskResult> future : futures) {
                    TaskResult result = future.get();
                    if (result.cpuTime > maxIterCpuTime) {
                        maxIterCpuTime = result.cpuTime;
                    }
                    if (result.solution.f < bestIterCost) {
                        bestIterCost = result.solution.f;
                        bestIterSolution = result.solution;
                        bestPerturbationUsed = result.perturbationUsed;
                    }
                }

                totalWorkerCpuTime += maxIterCpuTime;

                if (bestIterSolution != null) {
                    solution.clone(bestIterSolution);
                    distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolutions[0]);

                    evaluateSolution(); // 内部触发输出

                    distAdjustment.distAdjustment(totalWorkerCpuTime);
                    if (bestPerturbationUsed != null) {
                        bestPerturbationUsed.getChosenOmega().setDistance(distanceLS);
                    }
                    if (acceptanceCriterion.acceptSolution(solution, totalWorkerCpuTime)) {
                        for (int k = 0; k < numThreads; k++) {
                            referenceSolutions[k].clone(solution);
                        }
                    }
                }

            } catch (InterruptedException | ExecutionException e) {
                e.printStackTrace();
            }
        }

        long mainCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
        long totalCpuTime = mainCpuTime + totalWorkerCpuTime;
        totalTime = (double) totalCpuTime / 1_000_000_000.0;

        executorService.shutdown();
        try {
            if (!executorService.awaitTermination(60, TimeUnit.SECONDS)) executorService.shutdownNow();
        } catch (InterruptedException e) { executorService.shutdownNow(); }

        writeFinalSolutionToFile();
        closeCSVFile();
    }

    public void evaluateSolution() {
        if ((solution.f - bestF) < -epsilon) {
            if (solution != null && solution.routes != null) {
                bestF = solution.f;
                bestSolution.clone(solution);
                iteratorMF = iterator;

                long mainCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
                long totalCpuTime = mainCpuTime + totalWorkerCpuTime;
                timeAF = (double) totalCpuTime / 1_000_000_000.0;

                if (print) {
                    System.out.println(timeAF + ";" + bestF);
                }

                // 同步输出逻辑
                writeToCSV(timeAF, bestF);
                // 默认更新最优解文件
                writeSolutionToFile(bestF, timeAF);
            }
        }
    }

    private boolean stoppingCriterion() {
        switch (stoppingCriterionType) {
            case Iteration:
                if (bestF <= optimal || executionMaximumLimit <= iterator) return true;
                break;
            case Time:
                long mainCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
                long totalCpuTime = mainCpuTime + totalWorkerCpuTime;
                double elapsedCpuSeconds = (double) totalCpuTime / 1_000_000_000.0;
                if (bestF <= optimal || executionMaximumLimit < elapsedCpuSeconds) return true;
                break;
        }
        return false;
    }

    public void setInstanceName(String instanceName) {
        // 如果没有手动设置 -output，则使用默认的目录结构
        if (!customOutputSet) {
            this.outputDirectory = "Results/" + instanceName + "/";
        }
        this.instanceName = instanceName;
        initializeOutputDirectory();
        initializeCSVFile();
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        int numThreads = 2;
        String instanceName = "default";
        String customOutput = null; // 新增：记录命令行传来的 output 路径

        for (int i = 0; i < args.length; i++) {
            if (args[i].equals("-file") && i + 1 < args.length) {
                File file = new File(args[i + 1]);
                String fileName = file.getName();
                instanceName = fileName.contains(".") ? fileName.substring(0, fileName.lastIndexOf(".")) : fileName;
            }
            if (args[i].equals("-threads") && i + 1 < args.length) {
                try { numThreads = Integer.parseInt(args[i + 1]); } catch (Exception e) {}
            }
            // 新增：解析 -output 参数
            if (args[i].equals("-output") && i + 1 < args.length) {
                customOutput = args[i + 1];
            }
        }

        if (numThreads < 1) numThreads = 1;
        AILSII ailsII = new AILSII(reader, numThreads);

        // 先处理输出路径，再处理实例名
        if (customOutput != null) {
            ailsII.setOutputDirectory(customOutput);
        }
        ailsII.setInstanceName(instanceName);

        System.out.println("Running with " + numThreads + " threads. Instance: " + instanceName);
        ailsII.search();
    }
    public Solution getBestSolution() { return bestSolution; }
    public double getBestF() { return bestF; }
    public double getGap() { return 100 * ((bestF - optimal) / optimal); }
    public boolean isPrint() { return print; }
    public void setPrint(boolean print) { this.print = print; }
    public boolean isOutputAllSolutions() { return outputAllSolutions; }
    public void setOutputAllSolutions(boolean outputAllSolutions) { this.outputAllSolutions = outputAllSolutions; }
    public Solution getSolution() { return solution; }
    public int getIterator() { return iterator; }

    public String printOmegas() {
        String str = "";
        // 使用 distinctPerturbations 打印不重复的算子信息
        for (int i = 0; i < distinctPerturbations.length; i++) {
            if (distinctPerturbations[i] != null) {
                // key 使用枚举值 + 路线数
                str += "\n" + omegaSetup.get(distinctPerturbations[i].perturbationType + "" + referenceSolutions[0].numRoutes);
            }
        }
        return str;
    }

    public Perturbation[] getPertubOperators() { return distinctPerturbations; }
    public double getTotalTime() { return totalTime; }
    public double getTimePerIteration() { return totalTime / iterator; }
    public double getTimeAF() { return timeAF; }
    public int getIteratorMF() { return iteratorMF; }
    public double getConvergenceIteration() { return (double) iteratorMF / iterator; }
    public double convergenceTime() { return (double) timeAF / totalTime; }
}