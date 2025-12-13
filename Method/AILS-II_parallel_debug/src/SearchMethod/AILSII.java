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
import Perturbation.PerturbationType; // 导入 Config 中使用的枚举
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
        final long cpuTime; // 纳秒
        final Perturbation perturbationUsed; // 记录产生该解的扰动算子

        TaskResult(Solution solution, long cpuTime, Perturbation perturbationUsed) {
            this.solution = solution;
            this.cpuTime = cpuTime;
            this.perturbationUsed = perturbationUsed;
        }
    }

    //----------核心变量------------
    int numThreads; // 并行线程数
    Solution solution, bestSolution;

    // 将原有的独立变量改为数组，支持动态线程数
    Solution[] referenceSolutions;
    Instance[] instances;

    // 每个线程独立的算子和搜索组件
    Perturbation[] threadPerturbations;
    FeasibilityPhase[] feasibilityOperators;
    LocalSearch[] localSearches;
    IntraLocalSearch[] intraLocalSearches;

    // 用于 printOmegas 和 Setup 的去重扰动算子列表
    // (通常用于存储 Config 中定义的那几个基础类型的实例化引用)
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
    Random pertRand = new Random(42); // 专门用于选择扰动算子的随机数生成器

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
    private String instanceName = "default";
    private FileWriter csvWriter;

    private ExecutorService executorService;
    private Config config;

    /**
     * 构造函数修改：接收 reader 和 numThreads，内部初始化数组
     */
    public AILSII(InputParameters reader, int numThreads)
    {
        this.numThreads = numThreads;
        Config config = reader.getConfig();
        this.config = config;

        // 1. 初始化线程池
        this.executorService = Executors.newFixedThreadPool(numThreads);

        this.optimal = reader.getBest();
        this.executionMaximumLimit = reader.getTimeLimit();
        this.threadMXBean = ManagementFactory.getThreadMXBean();

        this.epsilon = config.getEpsilon();
        this.stoppingCriterionType = config.getStoppingCriterionType();
        this.idealDist = new IdealDist();
        this.numIterUpdate = config.getGamma();
        this.pairwiseDistance = new Distance();

        // 2. 初始化主实例（用于非并行部分的全局维护）
        // 我们创建一个主 Instance 用于 bestSolution 等，避免多线程竞争
        Instance mainInstance = new Instance(reader);
        this.solution = new Solution(mainInstance, config);
        this.bestSolution = new Solution(mainInstance, config);

        this.distAdjustment = new DistAdjustment(idealDist, config, executionMaximumLimit);
        this.constructSolution = new ConstructSolution(mainInstance, config);
        this.acceptanceCriterion = new AcceptanceCriterion(mainInstance, config, executionMaximumLimit);

        // 3. 初始化 OmegaAdjustment (共享资源)
        // 获取 Config 中的扰动类型数组 (PerturbationType[])
        PerturbationType[] definedTypes = config.getPerturbation();

        // 我们需要保存这些类型的引用以便 printOmegas 使用
        this.distinctPerturbations = new Perturbation[definedTypes.length];

        for (int i = 0; i < definedTypes.length; i++)
        {
            // 注意：这里使用 definedTypes[i] + "" 将 Enum 转为 String 作为 Key
            OmegaAdjustment newOmegaAdjustment = new OmegaAdjustment(definedTypes[i], config, mainInstance.getSize(), idealDist);
            omegaSetup.put(definedTypes[i] + "", newOmegaAdjustment);
        }

        // 4. 初始化并行数组
        this.instances = new Instance[numThreads];
        this.referenceSolutions = new Solution[numThreads];
        this.intraLocalSearches = new IntraLocalSearch[numThreads];
        this.localSearches = new LocalSearch[numThreads];
        this.feasibilityOperators = new FeasibilityPhase[numThreads];
        this.threadPerturbations = new Perturbation[numThreads];

        // 5. 循环为每个线程分配资源
        for (int i = 0; i < numThreads; i++) {
            // A. 创建独立的 Instance (确保线程安全)
            this.instances[i] = new Instance(reader);

            // B. 创建组件
            this.referenceSolutions[i] = new Solution(this.instances[i], config);
            this.intraLocalSearches[i] = new IntraLocalSearch(this.instances[i], config);
            this.localSearches[i] = new LocalSearch(this.instances[i], config, this.intraLocalSearches[i]);
            this.feasibilityOperators[i] = new FeasibilityPhase(this.instances[i], config, this.intraLocalSearches[i]);

            // C. 分配扰动算子 (关键逻辑修改)
            PerturbationType pType;
            if (i < definedTypes.length) {
                // 如果线程索引在定义的类型范围内，按顺序分配 (0->Type0, 1->Type1)
                pType = definedTypes[i];
            } else {
                // 如果线程数 > 定义的类型数，随机选择一个
                int randIndex = pertRand.nextInt(definedTypes.length);
                pType = definedTypes[randIndex];
            }

            try {
                // D. 反射实例化
                // 注意：Config 返回的是 PerturbationType 枚举，我们需要拼接类名 "Perturbation." + pType
                this.threadPerturbations[i] = (Perturbation) Class.forName("Perturbation." + pType)
                        .getConstructor(Instance.class, Config.class, HashMap.class, IntraLocalSearch.class)
                        .newInstance(this.instances[i], config, omegaSetup, this.intraLocalSearches[i]);

                // 如果这个是在 distinct 列表里的位置（前N个），保存引用用于打印
                if (i < definedTypes.length) {
                    this.distinctPerturbations[i] = this.threadPerturbations[i];
                }

            } catch (Exception e) {
                e.printStackTrace();
                throw new RuntimeException("扰动算子初始化失败: " + pType, e);
            }
        }

        initializeOutputDirectory();
    }

    //----------文件输出辅助方法 (保持原有逻辑)------------
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
            if (print) {
                System.out.println("Solution saved to: " + fullPath);
            }
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

        // 1. 初始化每个线程的参考解
        for (int i = 0; i < numThreads; i++) {
            referenceSolutions[i].numRoutes = instances[i].getMinNumberRoutes();
            constructSolution.construct(referenceSolutions[i]);
            feasibilityOperators[i].makeFeasible(referenceSolutions[i]);
            // 简单逻辑：根据奇偶性决定是否完全执行 localSearch，或者全部为 true
            // 原代码逻辑：thread1 true, thread2 false (或其他)。
            // 这里我们为了通用性，可以让所有线程初始都做 LS，或者保留交替逻辑
            boolean doFullLS = true;
            localSearches[i].localSearch(referenceSolutions[i], doFullLS);
        }

        // 2. 选取所有初始化解中最好的
        bestSolution.clone(referenceSolutions[0]);
        bestF = bestSolution.f;

        for(int i = 1; i < numThreads; i++) {
            if (referenceSolutions[i].f < bestF) {
                bestSolution.clone(referenceSolutions[i]);
                bestF = referenceSolutions[i].f;
            }
        }

        if (outputAllSolutions) {
            double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
            if (print) {
                System.out.println("Initial solution: " + initialTime + ";" + bestF);
            }
            writeSolutionToFile(bestF, initialTime);
        }

        // 3. 主循环
        while (!stoppingCriterion()) {
            iterator++;

            // A. 创建任务列表
            List<Callable<TaskResult>> tasks = new ArrayList<>();

            for (int i = 0; i < numThreads; i++) {
                final int threadIdx = i;
                tasks.add(() -> {
                    long taskStartTime = threadMXBean.getCurrentThreadCpuTime();

                    // 创建线程专属的临时 Solution
                    Solution threadSolution = new Solution(instances[threadIdx], config);
                    threadSolution.clone(referenceSolutions[threadIdx]);

                    // 执行扰动和搜索
                    threadPerturbations[threadIdx].applyPerturbation(threadSolution);
                    feasibilityOperators[threadIdx].makeFeasible(threadSolution);
                    localSearches[threadIdx].localSearch(threadSolution, true);

                    long taskEndTime = threadMXBean.getCurrentThreadCpuTime();
                    // 返回结果，包括使用的扰动算子引用
                    return new TaskResult(threadSolution, taskEndTime - taskStartTime, threadPerturbations[threadIdx]);
                });
            }

            // B. 并行执行
            try {
                List<Future<TaskResult>> futures = executorService.invokeAll(tasks);

                Solution bestIterSolution = null;
                Perturbation bestPerturbationUsed = null;
                double bestIterCost = Double.MAX_VALUE;

                // C. 处理结果
                for (Future<TaskResult> future : futures) {
                    TaskResult result = future.get();

                    // 累计 CPU 时间 (根据你的逻辑，累加所有线程的时间)
                    totalWorkerCpuTime += result.cpuTime;

                    // 寻找本次迭代中最优的解
                    if (result.solution.f < bestIterCost) {
                        bestIterCost = result.solution.f;
                        bestIterSolution = result.solution;
                        bestPerturbationUsed = result.perturbationUsed;
                    }
                }

                // D. 更新全局状态
                if (bestIterSolution != null) {
                    solution.clone(bestIterSolution); // 将最好的并行解复制到主解

                    // 计算距离 (与第一个参考解比较，保持简单)
                    distanceLS = pairwiseDistance.pairwiseSolutionDistance(solution, referenceSolutions[0]);

                    evaluateSolution(); // 检查是否刷新全局最优

                    distAdjustment.distAdjustment(totalWorkerCpuTime);

                    if (bestPerturbationUsed != null) {
                        bestPerturbationUsed.getChosenOmega().setDistance(distanceLS);
                    }

                    // 接受准则
                    if (acceptanceCriterion.acceptSolution(solution, totalWorkerCpuTime)) {
                        // 如果被接受，将该解广播给所有线程的 referenceSolution
                        for (int k = 0; k < numThreads; k++) {
                            referenceSolutions[k].clone(solution);
                        }
                    }
                }

            } catch (InterruptedException | ExecutionException e) {
                System.err.println("并行任务执行出错: " + e.getMessage());
                e.printStackTrace();
            }
        }

        // 4. 结束处理
        long mainCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
        long totalCpuTime = mainCpuTime + totalWorkerCpuTime;
        totalTime = (double) totalCpuTime / 1_000_000_000.0;

        executorService.shutdown();
        try {
            if (!executorService.awaitTermination(60, TimeUnit.SECONDS)) {
                executorService.shutdownNow();
            }
        } catch (InterruptedException e) {
            executorService.shutdownNow();
        }

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

                writeToCSV(timeAF, bestF);

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
                long mainCpuTime = threadMXBean.getCurrentThreadCpuTime() - first;
                long totalCpuTime = mainCpuTime + totalWorkerCpuTime;
                double elapsedCpuSeconds = (double) totalCpuTime / 1_000_000_000.0;

                if (bestF <= optimal || executionMaximumLimit < elapsedCpuSeconds)
                    return true;
                break;
        }
        return false;
    }

    public void setInstanceName(String instanceName) {
        this.outputDirectory = "Results/" + instanceName + "/";
        this.instanceName = instanceName;
        initializeOutputDirectory();
        initializeCSVFile();
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        // 默认线程数
        int numThreads = 2;

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
            }
            // 新增：解析线程数参数
            if (args[i].equals("-threads") && i + 1 < args.length) {
                try {
                    numThreads = Integer.parseInt(args[i + 1]);
                } catch (NumberFormatException e) {
                    System.err.println("无效的线程数，使用默认值 2");
                }
            }
        }

        // 保证至少1个线程
        if (numThreads < 1) numThreads = 1;
        System.out.println("Running with " + numThreads + " threads.");

        // 使用新的构造函数，传入线程数
        AILSII ailsII = new AILSII(reader, numThreads);

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