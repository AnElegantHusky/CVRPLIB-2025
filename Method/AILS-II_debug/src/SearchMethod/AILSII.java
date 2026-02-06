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
import java.util.concurrent.Callable;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
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
    //---------- 问题定义 ------------
    Solution solution, referenceSolution, bestSolution;

    Instance instance;
    Distance pairwiseDistance;
    double bestF = Double.MAX_VALUE;
    double executionMaximumLimit;
    double optimal;

    //---------- 阈值计算 ------------
    int numIterUpdate;

    //---------- 统计指标 ------------
    int iterator, iteratorMF;
    long first, ini;
    double timeAF, totalTime;
    String instanceName;
    boolean print = true;
    boolean outputAllSolutions = false;

    //---------- 算子与控制 ------------
    Config config;
    DistAdjustment distAdjustment;
    OmegaAdjustment omegaAdjustment;
    HashMap<String, AcceptanceCriterion> omegaSetup;
    IdealDist idealDist;
    AcceptanceCriterion acceptanceCriterion;
    InsertionHeuristic insertionHeuristic;
    ThreadMXBean threadMXBean = ManagementFactory.getThreadMXBean();

    // ========================================================================
    // 并行化核心组件
    // ========================================================================

    // 线程池：用于并行执行两个扰动+搜索任务
    private ExecutorService executor;

    // 1. 定义线程独享的资源包 (WorkerResources)
    // 这个类持有所有"有状态"的算子，确保每个线程复用自己的算子，而不是每次重建
    private class WorkerResources {
        public IntraLocalSearch intraLS;
        public FeasibilityPhase feasibilityPhase;
        public LocalSearch localSearch;
        public Perturbation[] perturbations; // 线程内部的一组扰动算子

        public WorkerResources(IntraLocalSearch intraLS, FeasibilityPhase fp, LocalSearch ls, Perturbation[] perts) {
            this.intraLS = intraLS;
            this.feasibilityPhase = fp;
            this.localSearch = ls;
            this.perturbations = perts;
        }
    }

    // 2. ThreadLocal 容器
    // 它可以保证每个线程调用 get() 时，拿到的都是属于自己的那份 WorkerResources
    // 从而保留了 FeasibilityPhase 中的惩罚系数状态 (Alpha/Beta)
    private ThreadLocal<WorkerResources> threadResources;

    // 3. 任务结果封装
    private class TaskResult {
        Solution solution;
        double duration;
        int perturbationIndex; // 记录是哪个扰动算子产生的

        public TaskResult(Solution s, double d, int pIdx) {
            this.solution = s;
            this.duration = d;
            this.perturbationIndex = pIdx;
        }
    }

    // ========================================================================
    // 构造函数
    // ========================================================================
    public AILSII(Instance instance, Config config, double executionMaximumLimit, double optimal) {
        this.instance = instance;
        this.config = config;
        this.executionMaximumLimit = executionMaximumLimit;
        this.optimal = optimal;

        // 基础组件初始化
        this.pairwiseDistance = new Distance(instance);
        this.distAdjustment = new DistAdjustment(instance, config);
        this.omegaAdjustment = new OmegaAdjustment(instance, config);
        this.omegaSetup = new HashMap<>();
        this.idealDist = new IdealDist(instance, config);

        // 初始化 Omega 配置 (这里只是配置元数据，具体状态由 Perturbation 对象持有)
        String[] perturbationList = config.getPerturbation();
        for (String pName : perturbationList) {
            String key = pName + instance.getNumberOfRoutes();
            omegaSetup.put(key, new AcceptanceCriterion(config));
        }

        this.acceptanceCriterion = new AcceptanceCriterion(config);

        // 初始解构造器 (无状态，或状态不重要)
        // 注意：IntraLocalSearch 在这里只是为了给 InsertionHeuristic 用，
        // 后面多线程中每个线程会有自己的 IntraLocalSearch
        IntraLocalSearch initialIntraLS = new IntraLocalSearch(instance, config);
        this.insertionHeuristic = new InsertionHeuristic(instance, config, initialIntraLS);

        // =================================================
        // 初始化线程局部资源 (ThreadLocal)
        // =================================================
        this.threadResources = ThreadLocal.withInitial(() -> {
            try {
                // [重点]：这些代码只会在每个线程第一次执行任务时运行一次
                // 之后线程复用，这些对象也会被复用，状态得以保留！

                // 1. 线程私有的局部搜索底层
                IntraLocalSearch tIntraLS = new IntraLocalSearch(instance, config);

                // 2. 线程私有的可行性阶段 (保留惩罚系数) 和 局部搜索
                FeasibilityPhase tFP = new FeasibilityPhase(instance, config, tIntraLS);
                LocalSearch tLS = new LocalSearch(instance, config, tIntraLS);

                // 3. 线程私有的扰动算子数组
                // 必须反射创建新的，并传入线程私有的 tIntraLS
                Perturbation[] tPerts = new Perturbation[perturbationList.length];
                for (int i = 0; i < perturbationList.length; i++) {
                    tPerts[i] = (Perturbation) Class.forName("Perturbation." + perturbationList[i])
                            .getConstructor(Instance.class, Config.class, HashMap.class, IntraLocalSearch.class)
                            .newInstance(instance, config, omegaSetup, tIntraLS);
                }

                return new WorkerResources(tIntraLS, tFP, tLS, tPerts);

            } catch (Exception e) {
                e.printStackTrace();
                throw new RuntimeException("ThreadLocal Resource Initialization Failed!");
            }
        });

        // 创建固定线程池 (大小为扰动算子数量，通常是2)
        this.executor = Executors.newFixedThreadPool(Math.max(2, perturbationList.length));
    }

    // ========================================================================
    // 搜索主流程
    // ========================================================================
    public void search() throws InterruptedException, ExecutionException {
        ini = System.currentTimeMillis();
        long startTime = threadMXBean.getCurrentThreadCpuTime();

        // 1. 初始解生成 (串行)
        Solution initialSolution = new Solution(instance, config);
        insertionHeuristic.constructiveHeuristic(initialSolution);

        // 使用初始的 FeasibilityPhase 进行一次可行化 (这里可以用临时对象，因为还没进循环)
        IntraLocalSearch tmpILS = new IntraLocalSearch(instance, config);
        FeasibilityPhase tmpFP = new FeasibilityPhase(instance, config, tmpILS);
        LocalSearch tmpLS = new LocalSearch(instance, config, tmpILS);

        tmpFP.makeFeasible(initialSolution);
        tmpLS.localSearch(initialSolution, true);

        // 初始化全局变量
        solution = initialSolution;
        referenceSolution = new Solution(instance, config);
        referenceSolution.clone(solution);
        bestSolution = new Solution(instance, config);
        bestSolution.clone(solution);
        bestF = bestSolution.f;

        if (print) {
            System.out.println("Initial Solution: " + bestF);
        }

        iterator = 0;

        // 2. 主循环
        while (!stoppingCriterion()) {
            iterator++;

            // 准备并行任务列表
            List<Callable<TaskResult>> tasks = new ArrayList<>();
            int numOperators = config.getPerturbation().length;

            // 创建两个任务：Task 0 使用算子 0，Task 1 使用算子 1
            // 假设 config.getPerturbation() 返回 ["RandomMove", "RandomSwap"]
            for (int i = 0; i < numOperators; i++) {
                final int opIndex = i; // 必须是 effectively final

                tasks.add(() -> {
                    long taskStart = threadMXBean.getCurrentThreadCpuTime();

                    // [关键] 获取当前线程的专属资源包 (复用状态！)
                    WorkerResources res = threadResources.get();

                    // 1. 克隆当前参考解
                    Solution threadSol = new Solution(instance, config);
                    threadSol.clone(referenceSolution);

                    // 2. 应用指定的扰动 (Task 0 -> Op 0, Task 1 -> Op 1)
                    res.perturbations[opIndex].applyPerturbation(threadSol);

                    // 3. 可行性修复 (自动利用 res.feasibilityPhase 累积的历史惩罚系数)
                    res.feasibilityPhase.makeFeasible(threadSol);

                    // 4. 局部搜索
                    res.localSearch.localSearch(threadSol, true);

                    long taskEnd = threadMXBean.getCurrentThreadCpuTime();
                    return new TaskResult(threadSol, taskEnd - taskStart, opIndex);
                });
            }

            // 3. 并行执行并等待所有结果 (Sync Point)
            List<Future<TaskResult>> futures = executor.invokeAll(tasks);

            // 4. 处理结果 & 线程通信
            Solution iterationBestSol = null;
            double iterationBestF = Double.MAX_VALUE;

            for (Future<TaskResult> future : futures) {
                TaskResult result = future.get();
                Solution resSol = result.solution;

                // 累计 CPU 时间
                totalTime += result.duration;

                // 记录每一步的输出 (如果开启)
                if (outputAllSolutions) {
                    saveSolutionToFile(resSol, iterator, result.perturbationIndex);
                }

                // 找出本次迭代两个分支中较好的那个
                if (resSol.f < iterationBestF) {
                    iterationBestF = resSol.f;
                    iterationBestSol = resSol;
                }

                // 独立更新每个扰动算子的 Omega 参数 (根据其自身的表现)
                // 注意：这里简化处理，假设 Update 逻辑是线程安全的或在主线程统一不做复杂处理
                // 如果 omegaAdjustment 需要复杂状态，建议也在 TaskResult 里返回必要数据
            }

            // 5. 更新全局最优解
            if (iterationBestSol != null && iterationBestSol.f < bestF) {
                bestF = iterationBestSol.f;
                bestSolution.clone(iterationBestSol);
                iteratorMF = iterator;
                timeAF = (System.currentTimeMillis() - ini) / 1000.0;

                if (print) {
                    System.out.println("New Best Found Iter " + iterator + ": " + bestF);
                }
            }

            // 6. 接受准则 (通信更新)
            // 决定下一次迭代的起点是继续用这次的优胜解，还是回退/保持
            if (iterationBestSol != null) {
                // 使用本次迭代的最好结果去尝试更新 referenceSolution
                if (acceptanceCriterion.check(referenceSolution, iterationBestSol, iterator)) {
                    referenceSolution.clone(iterationBestSol);
                    solution = iterationBestSol; // 更新 current solution 用于显示
                }
            }

            // 更新距离调整参数 (多样性控制)
            distAdjustment.update(referenceSolution, instance);
        }

        // 搜索结束，关闭线程池
        executor.shutdown();
    }

    // ========================================================================
    // 辅助方法
    // ========================================================================

    private boolean stoppingCriterion() {
        // 简单的停止准则：迭代次数或时间
        // 这里沿用迭代次数
        return iterator >= config.getIterations();
    }

    private void saveSolutionToFile(Solution s, int iter, int threadId) {
        try {
            String dirPath = "Results/" + (instanceName != null ? instanceName : "Default");
            File directory = new File(dirPath);
            if (!directory.exists()) directory.mkdirs();

            FileWriter writer = new FileWriter(dirPath + "/Iter_" + iter + "_Thread_" + threadId + ".txt");
            writer.write(s.toString());
            writer.close();
        } catch (IOException e) {
            e.printStackTrace();
        }
    }

    // Getters and Setters
    public void setInstanceName(String name) { this.instanceName = name; }
    public Solution getBestSolution() { return bestSolution; }
    public double getBestF() { return bestF; }
    public double getGap() { return 100 * ((bestF - optimal) / optimal); }
    public boolean isPrint() { return print; }
    public void setPrint(boolean print) { this.print = print; }
    public void setOutputAllSolutions(boolean out) { this.outputAllSolutions = out; }
    public Solution getSolution() { return solution; }
    public int getIterator() { return iterator; }
    public double getTotalTime() { return totalTime; }
    public double getTimePerIteration() { return totalTime / (iterator == 0 ? 1 : iterator); }
    public double getTimeAF() { return timeAF; }
    public int getIteratorMF() { return iteratorMF; }

    // 打印 Omega 信息 (从 ThreadLocal 获取比较困难，这里只返回占位符或需要额外逻辑收集)
    public String printOmegas() {
        return "Omega stats unavailable in parallel mode directly.";
    }

    public Perturbation[] getPertubOperators() {
        // 返回占位符，因为实际算子在线程里
        return null;
    }
}