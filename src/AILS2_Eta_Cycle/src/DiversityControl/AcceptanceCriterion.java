/**
 * Copyright 2022, Vinícius R. Máximo
 * Distributed under the terms of the MIT License.
 * SPDX-License-Identifier: MIT
 */
package DiversityControl;

import Auxiliary.Mean;
import Data.Instance;
import SearchMethod.Config;
import SearchMethod.StoppingCriterionType;
import Solution.Solution;
import java.lang.management.ManagementFactory;
import java.lang.management.ThreadMXBean;

public class AcceptanceCriterion {
    double thresholdOF;
    double eta, etaMin, etaMax;
    long ini;
    double alpha = 1;
    int globalIterator = 0;
    StoppingCriterionType stoppingCriterionType;

    // 时间与周期控制参数
    double totalExecutionLimit;
    double cycleTime;
    double etaResetPercentage;
    double initialEtaMax; // 初始的 EtaMax，作为基准
    double currentEtaMax; // 当前衰减后的 EtaMax 基准
    int currentCycleIndex = 0;

    // --- [NEW] 新增策略参数 ---
    double lastBestTime = 0.0; // 上次找到最优解的时间点（秒）
    double resetThreshold;     // 策略1的阈值（秒）
    double convergenceFactor;  // 策略3的收敛系数 (0.0 - 1.0)
    int resetCount = 0;        // 记录重置了多少次

    int numIterUpdate;
    double upperLimit = Integer.MAX_VALUE, updatedUpperLimit = Integer.MAX_VALUE;
    Mean averageLSfunction;
    ThreadMXBean threadMXBean;

    // 修改构造函数，接收新参数
    public AcceptanceCriterion(Instance instance, Config config, Double totalExecutionLimit, Double cycleTime, Double etaResetPercentage, Double resetThreshold, Double convergenceFactor) {
        this.eta = config.getEtaMax();
        this.initialEtaMax = config.getEtaMax();
        this.currentEtaMax = this.initialEtaMax; // 初始时相等
        this.etaMin = config.getEtaMin();
        this.etaMax = config.getEtaMax();
        this.stoppingCriterionType = config.getStoppingCriterionType();
        this.averageLSfunction = new Mean(config.getGamma());
        this.numIterUpdate = config.getGamma();

        this.totalExecutionLimit = totalExecutionLimit;

        // 确保周期时间有效
        if (cycleTime == null || cycleTime <= 0 || cycleTime > totalExecutionLimit) {
            this.cycleTime = totalExecutionLimit;
        } else {
            this.cycleTime = cycleTime;
        }

        this.etaResetPercentage = (etaResetPercentage != null) ? etaResetPercentage : 1.0;

        // [NEW] 初始化新参数
        this.resetThreshold = (resetThreshold != null) ? resetThreshold : 0.0;
        this.convergenceFactor = (convergenceFactor != null) ? convergenceFactor : 1.0;

        this.threadMXBean = ManagementFactory.getThreadMXBean();
    }

    // [NEW] 提供给 AILSII 调用的方法，当找到新 Best 时更新时间
    public void setLastBestTime(double timeInSeconds) {
        this.lastBestTime = timeInSeconds;
    }

    public boolean acceptSolution(Solution solution) {
        if (globalIterator == 0) {
            ini = threadMXBean.getCurrentThreadCpuTime();
        }

        averageLSfunction.setValue(solution.f);
        globalIterator++;

        // 更新上下界逻辑
        if (globalIterator % numIterUpdate == 0) {
            upperLimit = updatedUpperLimit;
            updatedUpperLimit = Integer.MAX_VALUE;
        }
        if (solution.f < updatedUpperLimit) {
            updatedUpperLimit = solution.f;
        }
        if (solution.f < upperLimit) {
            upperLimit = solution.f;
        }

        // ==========================================
        //         Eta 更新与重置核心逻辑
        // ==========================================

        if (stoppingCriterionType == StoppingCriterionType.Time) {
            // 1. 获取当前运行秒数
            double currentTotalTime = (double) (threadMXBean.getCurrentThreadCpuTime() - ini) / 1_000_000_000;

            // 2. 检查周期跨越
            int calculatedCycle = (int) (currentTotalTime / cycleTime);

            if (calculatedCycle > currentCycleIndex) {
                // 进入了新的周期节点，判断是否执行重置
                double timeSinceLastBest = currentTotalTime - this.lastBestTime;
                boolean shouldReset = true; // 默认应该重置，除非满足保留条件

                // 策略 1: 检查是否位于 [0, threshold] 之间
//                if (timeSinceLastBest >= 0 && timeSinceLastBest <= this.resetThreshold) {
                if (timeSinceLastBest <= this.resetThreshold) {
                    shouldReset = false;
                    System.out.println(">>> SKIP RESET (Policy 1): Recently found best solution (" + String.format("%.2f", timeSinceLastBest) + "s ago).");
                }

                // 策略 2: 检查是否属于 [cycle, 2*cycle] 区间
                // 这里的逻辑是：如果虽然很久没更新，但刚好处于"观察期"（1倍到2倍周期之间），认为还在下降中途
                if (shouldReset && (timeSinceLastBest >= this.cycleTime && timeSinceLastBest <= 2 * this.cycleTime)) {
                    shouldReset = false;
                    System.out.println(">>> SKIP RESET (Policy 2): Within grace period [cycle, 2*cycle]. Time since best: " + String.format("%.2f", timeSinceLastBest));
                }

                // 如果 timeSinceLastBest > 2 * cycleTime，shouldReset 保持 true (认为卡住)
                // 如果 resetThreshold < timeSinceLastBest < cycleTime，shouldReset 保持 true (正常周期重置)

                if (shouldReset) {
                    // 策略 3: 设置收敛系数，随着重置次数增加，降低 etaMax
                    this.resetCount++;
                    this.currentEtaMax = this.initialEtaMax * Math.pow(this.convergenceFactor, this.resetCount);

                    // 执行重置
                    this.eta = this.currentEtaMax * this.etaResetPercentage;

                    System.out.println(">>> ETA RESET TRIGGERED at " + String.format("%.2f", currentTotalTime) + "s. " +
                            "Reset#" + resetCount + " New EtaBase: " + String.format("%.4f", currentEtaMax) + " New Eta: " + String.format("%.4f", this.eta));

                    alpha = 1.0;
                } else {
                    // 如果跳过重置，我们只需更新周期索引，让它继续自然衰减
                }

                currentCycleIndex = calculatedCycle;
            }

            // 3. 计算衰减率 alpha
            if (globalIterator % numIterUpdate == 0) {
                double timeInCurrentCycle = currentTotalTime % cycleTime;
                if (timeInCurrentCycle <= 0.001) timeInCurrentCycle = 0.001;

                double iterPerSec = globalIterator / (currentTotalTime + 0.001);
                double totalStepsInCycle = iterPerSec * cycleTime;

                // 注意：这里衰减的起点应该是当前周期的起始 Eta (即 currentEtaMax * etaResetPercentage)
                double currentCycleStartEta = this.currentEtaMax * this.etaResetPercentage;

                // 防止除零或无效计算
                if(totalStepsInCycle > 0 && currentCycleStartEta > 0) {
                    alpha = Math.pow(etaMin / currentCycleStartEta, 1.0 / totalStepsInCycle);
                } else {
                    alpha = 1.0;
                }
            }
        }
        else if (stoppingCriterionType == StoppingCriterionType.Iteration) {
            // 迭代模式暂不应用复杂的时间策略
            if (globalIterator % numIterUpdate == 0) {
                alpha = Math.pow(etaMin / etaMax, (double) 1 / totalExecutionLimit);
            }
        }

        // 应用衰减
        eta *= alpha;
        eta = Math.max(eta, etaMin);

        thresholdOF = (int) (upperLimit + (eta * (averageLSfunction.getDynamicAverage() - upperLimit)));

        if (solution.f <= thresholdOF) {
            return true;
        } else {
            return false;
        }
    }

    public double getEta() { return eta; }
    public double getThresholdOF() { return thresholdOF; }
    public void setEta(double eta) { this.eta = eta; }
    public void setIdealFlow(double idealFlow) { }
}