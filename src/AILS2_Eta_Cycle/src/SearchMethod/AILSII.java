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
import java.io.FilenameFilter;

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

    // 参数
    double totalExecutionLimit;
    double cycleTime;
    double etaResetPercentage;
    boolean printEta = false;

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

    //----------文件输出配置------------
    private String outputDirectory = "Results/";
    private boolean customOutputSet = false;
    private String instanceName = "default";
    private FileWriter csvWriter;
    private String resumeSolPath = null;
    private String currentUniqueFilename = null;

    double resetThreshold;
    double convergenceFactor;

    public AILSII(Instance instance, InputParameters reader, double cycleTime, double etaResetPercentage, boolean printEta, double resetThreshold, double convergenceFactor)
    {
        this.instance=instance;
        Config config=reader.getConfig();
        this.optimal=reader.getBest();

        // 1. 初始化时间控制
        this.totalExecutionLimit = reader.getTimeLimit();
        // 如果未设置 cycleTime，默认为总时间
        this.cycleTime = (cycleTime > 0) ? cycleTime : this.totalExecutionLimit;
        this.etaResetPercentage = etaResetPercentage;
        this.printEta = printEta;

        this.resetThreshold = resetThreshold;
        this.convergenceFactor = convergenceFactor;

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

        // 注意：DistAdjustment 逻辑不变，仍用总时长
        this.distAdjustment=new DistAdjustment( idealDist, config, totalExecutionLimit);

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

        // 2. 初始化 AcceptanceCriterion，传入正确的周期参数
        this.acceptanceCriterion=new AcceptanceCriterion(instance, config,
                totalExecutionLimit,
                this.cycleTime,
                this.etaResetPercentage,
                this.resetThreshold,
                this.convergenceFactor
        );

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
            System.err.println("Error creating directory: " + e.getMessage());
        }
    }

    private String getUniqueFilename() {
        if (currentUniqueFilename != null) {
            return currentUniqueFilename;
        }

        String baseName = (instanceName == null || instanceName.trim().isEmpty()) ? "instance" : instanceName.trim();
        if (baseName.toLowerCase().endsWith(".sol")) {
            baseName = baseName.substring(0, baseName.length() - 4);
        }

        File dir = new File(outputDirectory);
        int maxIndex = 0;

        if (dir.exists() && dir.isDirectory()) {
            final String prefix = baseName + "_";
            final String suffix = ".sol";

            File[] files = dir.listFiles(new FilenameFilter() {
                @Override
                public boolean accept(File dir, String name) {
                    return name.startsWith(prefix) && name.toLowerCase().endsWith(suffix);
                }
            });

            if (files != null) {
                for (File f : files) {
                    String name = f.getName();
                    try {
                        String numberPart = name.substring(prefix.length(), name.length() - suffix.length());
                        int index = Integer.parseInt(numberPart);
                        if (index > maxIndex) {
                            maxIndex = index;
                        }
                    } catch (NumberFormatException e) {
                        // ignore
                    }
                }
            }
        }

        int nextIndex = maxIndex + 1;
        currentUniqueFilename = baseName + "_" + nextIndex + ".sol";
        return currentUniqueFilename;
    }

    private void initializeCSVFile() {
        try {
            String uniqueSolName = getUniqueFilename();
            String csvFilename = uniqueSolName.replace(".sol", ".csv");
            String csvFilePath = outputDirectory + csvFilename;
            csvWriter = new FileWriter(csvFilePath);
        } catch (IOException e) {
            System.err.println("Failed to create CSV: " + e.getMessage());
        }
    }

    private void writeToCSV(double time, double bestF, double currentEta) {
        if (csvWriter != null) {
            try {
                StringBuilder sb = new StringBuilder();
                sb.append(deci.format(time).replace(",", "."));
                sb.append(";");
                sb.append(deci.format(bestF).replace(",", "."));

                // 输出 Eta
                if (this.printEta) {
                    sb.append(";");
                    sb.append(deci.format(currentEta).replace(",", "."));
                }

                sb.append("\n");
                csvWriter.write(sb.toString());
                csvWriter.flush();
            } catch (IOException e) {
                System.err.println("Failed to write CSV: " + e.getMessage());
            }
        }
    }

    private void closeCSVFile() {
        if (csvWriter != null) {
            try {
                csvWriter.close();
            } catch (IOException e) {
                System.err.println("Failed to close CSV: " + e.getMessage());
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

    private void writeSolutionToFile(double currentBestF, double currentTime) {
        String filename = getUniqueFilename();
        String fullPath = outputDirectory + filename;

        try (FileWriter writer = new FileWriter(fullPath, false)) {
            for (int i = 0; i < bestSolution.numRoutes; i++) {
                String routeNodes = getRouteNodes(i);
                writer.write("Route #" + (i + 1) + ": " + routeNodes + "\n");
            }
            writer.write("Cost " + deci.format(currentBestF).replace(",", ".") + "\n");
            writer.write("Time " + deci.format(currentTime).replace(",", "."));
            writer.flush();
        } catch (IOException e) {
            System.err.println("Failed to write solution file: " + e.getMessage());
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public void search() {
        iterator = 0;
        first = threadMXBean.getCurrentThreadCpuTime();

        // Resume 逻辑
        if (this.resumeSolPath != null) {
            try {
                referenceSolution.loadSolutionCVRPLib(this.resumeSolPath);
                System.out.println("Resumed from: " + this.resumeSolPath);
            } catch (Exception e) {
                System.err.println("Resume failed: " + e.getMessage());
                return;
            }
        } else {
            referenceSolution.numRoutes = instance.getMinNumberRoutes();
            constructSolution.construct(referenceSolution);
            feasibilityOperator.makeFeasible(referenceSolution);
            localSearch.localSearch(referenceSolution, true);
        }

        bestSolution.clone(referenceSolution);
        bestF = bestSolution.f;

        double initialTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;
        if (print) {
            String etaStr = printEta ? (";" + acceptanceCriterion.getEta()) : "";
            System.out.println("Initial solution: " + initialTime + ";" + bestF + etaStr);
        }

        writeSolutionToFile(bestF, initialTime);

        // 主循环
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

            selectedPerturbation.getChosenOmega().setDistance(distanceLS);

            if (acceptanceCriterion.acceptSolution(solution))
                referenceSolution.clone(solution);
        }

        totalTime = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;

        writeSolutionToFile(bestF, totalTime);
        closeCSVFile();
    }

    public void evaluateSolution() {
        // 记录更好的解
        if ((solution.f - bestF) < -epsilon) {
            if (solution != null && solution.routes != null) {
                bestF = solution.f;
                bestSolution.clone(solution);
                iteratorMF = iterator;
                timeAF = (double) (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000;

                acceptanceCriterion.setLastBestTime(timeAF);

                double currentEta = acceptanceCriterion.getEta();

                if (print) {
                    String etaStr = printEta ? (";" + currentEta) : "";
                    System.out.println(timeAF + ";" + bestF + etaStr);
                }

                writeToCSV(timeAF, bestF, currentEta);
                writeSolutionToFile(bestF, timeAF);
            }
        }
    }

    private boolean stoppingCriterion() {
        switch (stoppingCriterionType) {
            case Iteration:
                if (bestF <= optimal || totalExecutionLimit <= iterator)
                    return true;
                break;

            case Time:
                // 主停止条件：基于总时间 totalExecutionLimit
                if (bestF <= optimal || totalExecutionLimit < (threadMXBean.getCurrentThreadCpuTime() - first) / 1_000_000_000)
                    return true;
                break;
        }
        return false;
    }

    public void setInstanceName(String instanceName) {
        this.instanceName = instanceName;
        if (!customOutputSet) {
            this.outputDirectory = "Results/" + instanceName + "/";
        }
        initializeOutputDirectory();
        initializeCSVFile();
    }

    public static void main(String[] args)
    {
        InputParameters reader = new InputParameters();
        reader.readingInput(args);

        Instance instance = new Instance(reader);

        String instanceName = "default";
        String customOutput = null;
        String resumePath = null;

        // 新参数默认值
        double cycleTimeArg = -1;
        double resetEtaArg = 1.0;
        boolean printEtaArg = false;

        // 参数解析
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
            if (args[i].equals("-output") && i + 1 < args.length) {
                customOutput = args[i + 1];
            }
            if (args[i].equals("-resume") && i + 1 < args.length) {
                resumePath = args[i + 1];
            }

            // [新] Cycle
            if (args[i].equals("-cycle") && i + 1 < args.length) {
                try {
                    cycleTimeArg = Double.parseDouble(args[i+1]);
                } catch (NumberFormatException e) {
                    System.err.println("Cycle must be a number");
                }
            }
            // [新] ResetEta
            if (args[i].equals("-resetEta") && i + 1 < args.length) {
                try {
                    resetEtaArg = Double.parseDouble(args[i+1]);
                } catch (NumberFormatException e) {
                    System.err.println("Reset Eta must be a number");
                }
            }
            // [新] PrintEta
            if (args[i].equals("-printEta") && i + 1 < args.length) {
                printEtaArg = Boolean.parseBoolean(args[i+1]);
            }
        }

        // [NEW] 新参数默认值
        double resetThresholdArg = 600.0; // 默认 600秒内找到最优解不重置
        double convergenceFactorArg = 0.95; // 默认每次重置衰减 5%

        AILSII ailsII = new AILSII(instance, reader, cycleTimeArg, resetEtaArg, printEtaArg, resetThresholdArg, convergenceFactorArg);

        if (customOutput != null) {
            ailsII.setOutputDirectory(customOutput);
        }

        ailsII.setInstanceName(instanceName);

        System.out.println("Start Search: " + instanceName);
        System.out.println("Config -> TotalTime: " + reader.getTimeLimit() +
                ", CycleTime: " + (cycleTimeArg > 0 ? cycleTimeArg : "Same as Total") +
                ", EtaReset: " + resetEtaArg +
                ", PrintEta: " + printEtaArg);

        if (resumePath != null) {
            ailsII.setResumePath(resumePath);
        }

        ailsII.search();
    }

    // Getters/Setters
    public void setResumePath(String path) { this.resumeSolPath = path; }
    public Solution getBestSolution() { return bestSolution; }
    public double getBestF() { return bestF; }
    public double getGap() { return 100*((bestF-optimal)/optimal); }
    public boolean isPrint() { return print; }
    public void setPrint(boolean print) { this.print = print; }
    public Solution getSolution() { return solution; }
    public int getIterator() { return iterator; }
    public String printOmegas() {
        String str="";
        for (int i = 0; i < pertubOperators.length; i++) {
            str+="\n"+omegaSetup.get(this.pertubOperators[i].perturbationType+""+referenceSolution.numRoutes);
        }
        return str;
    }
    public Perturbation[] getPertubOperators() { return pertubOperators; }
    public double getTotalTime() { return totalTime; }
    public double getTimePerIteration() { return totalTime/iterator; }
    public double getTimeAF() { return timeAF; }
    public int getIteratorMF() { return iteratorMF; }
    public double getConvergenceIteration() { return (double)iteratorMF/iterator; }
    public double convergenceTime() { return (double)timeAF/totalTime; }
}