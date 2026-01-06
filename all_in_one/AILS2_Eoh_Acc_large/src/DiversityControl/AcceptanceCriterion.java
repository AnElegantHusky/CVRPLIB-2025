package DiversityControl;

import Data.Instance;
import SearchMethod.Config;
import SearchMethod.StoppingCriterionType;
import Solution.Solution;

import java.util.ArrayDeque;
import java.util.Deque;

public class AcceptanceCriterion {

    /**
     * Defines the current operational phase of the acceptance criterion.
     */
    private enum SearchPhase {
        INTENSIFICATION, // Greedy search for local improvements.
        DIVERSIFICATION  // Lenient search to escape local optima.
    }

    // --- Phase Management ---
    private SearchPhase currentPhase;
    private int iterationsInCurrentPhase;
    private int maxDiversificationIterations; // The dynamically calculated budget for the current diversification phase.
    private final int intensificationStagnationLimit; // Iterations of no improvement to trigger diversification.

    // --- Adaptive Threshold Control ---
    private double diversificationThreshold; // The allowed deviation from the global best during diversification.
    private final double initialDiversificationThreshold;
    private final double minDiversificationThreshold;
    private final Deque<Double> diversificationMemory;
    private final int memorySize;
    private double sumOfMemoryCosts = 0.0;

    // --- Search State & History ---
    private double bestObjectiveSoFar = Double.POSITIVE_INFINITY;
    private double lastAcceptedObjective = Double.POSITIVE_INFINITY;
    private double bestObjectiveAtPhaseStart = Double.POSITIVE_INFINITY;
    private boolean isInitialized = false;

    // --- Configuration & Progress Tracking ---
    private long globalIterator = 0;
    private final StoppingCriterionType stoppingCriterionType;
    private final double executionMaximumLimit;
    private final long startTimeNano;

    /**
     * Constructs the Strategic Oscillation with Adaptive Phasing (SOAP) criterion.
     *
     * @param instance The problem instance (unused, for API compatibility).
     * @param config   The solver's configuration object.
     * @param executionMaximumLimit The maximum limit for the stopping criterion.
     */
    public AcceptanceCriterion(Instance instance, Config config, Double executionMaximumLimit) {
        // Map 'eta' parameters to the diversification threshold.
        this.initialDiversificationThreshold = config.getEtaMax();
        this.minDiversificationThreshold = config.getEtaMin();
        this.diversificationThreshold = this.initialDiversificationThreshold;

        // The intensification phase ends after `gamma` non-improving iterations.
        this.intensificationStagnationLimit = config.getGamma();
        // The memory for adapting the threshold is also based on `gamma`.
        this.memorySize = config.getGamma();
        this.diversificationMemory = new ArrayDeque<>(this.memorySize);

        // Start the search with aggressive intensification.
        this.currentPhase = SearchPhase.INTENSIFICATION;
        this.iterationsInCurrentPhase = 0;
        this.maxDiversificationIterations = this.intensificationStagnationLimit * 2; // Initial default value.

        // Retain for calculating search progress.
        this.stoppingCriterionType = config.getStoppingCriterionType();
        this.executionMaximumLimit = executionMaximumLimit;
        this.startTimeNano = System.nanoTime();
    }

    /**
     * Determines whether to accept a new candidate solution based on the current search phase.
     *
     * @param solution The candidate solution to evaluate.
     * @return {@code true} if the solution is accepted, {@code false} otherwise.
     */
    public boolean acceptSolution(Solution solution) {
        double currentObjective = solution.f;
        if (!isInitialized) {
            initializeState(currentObjective);
        }

        boolean isAccepted = false;
        // 1. Always accept a new global best solution, regardless of the current phase.
        if (currentObjective < bestObjectiveSoFar) {
            isAccepted = true;
            updateOnGlobalImprovement(currentObjective);
        } else {
            // 2. Apply phase-specific acceptance criteria.
            switch (currentPhase) {
                case INTENSIFICATION:
                    // Accept only if it's better than the *last accepted* solution (Greedy).
                    if (currentObjective < lastAcceptedObjective) {
                        isAccepted = true;
                    }
                    break;
                case DIVERSIFICATION:
                    // Accept if within the dynamic threshold of the *global best* solution.
                    if (currentObjective <= bestObjectiveSoFar + diversificationThreshold) {
                        isAccepted = true;
                    }
                    break;
            }
        }

        if (isAccepted) {
            lastAcceptedObjective = currentObjective;
            if (currentPhase == SearchPhase.DIVERSIFICATION) {
                updateMemory(currentObjective); // Track solution quality during diversification.
            }
        }

        // 3. Adapt the phase and parameters for the next iteration.
        adaptSearchPhase();

        globalIterator++;
        return isAccepted;
    }

    /**
     * Initializes the state with the objective of the first solution.
     */
    private void initializeState(double initialObjective) {
        this.bestObjectiveSoFar = initialObjective;
        this.lastAcceptedObjective = initialObjective;
        this.bestObjectiveAtPhaseStart = initialObjective;
        this.isInitialized = true;
    }

    /**
     * Updates state upon finding a new best-so-far solution.
     */
    private void updateOnGlobalImprovement(double newBestObjective) {
        bestObjectiveSoFar = newBestObjective;
        // Finding a new global best is a strong signal to intensify.
        if (currentPhase == SearchPhase.DIVERSIFICATION) {
            switchToIntensification();
        }
    }

    /**
     * Manages the transition between search phases based on progress and iteration budgets.
     */
    private void adaptSearchPhase() {
        iterationsInCurrentPhase++;

        if (currentPhase == SearchPhase.INTENSIFICATION) {
            // If intensification has stagnated, switch to diversification.
            if (iterationsInCurrentPhase > intensificationStagnationLimit) {
                switchToDiversification();
            }
        } else { // DIVERSIFICATION Phase
            // If the diversification budget is spent, switch back to intensification.
            if (iterationsInCurrentPhase > maxDiversificationIterations) {
                switchToIntensification();
            }
            // Adapt the threshold during the diversification phase for the next cycle.
            adaptDiversificationThreshold();
        }
    }

    /**
     * Transitions the search to the DIVERSIFICATION phase.
     * Calculates the duration of this new phase based on recent progress.
     */
    private void switchToDiversification() {
        // Calculate the quality improvement during the last intensification phase.
        double improvement = bestObjectiveAtPhaseStart - bestObjectiveSoFar;
        // If there was significant improvement, we don't need to diversify for long.
        // If improvement was minimal, we need a longer diversification period.
        if (improvement > 1e-9) { // Using a small epsilon to handle floating-point comparisons
            // Shorter diversification after successful intensification.
            this.maxDiversificationIterations = intensificationStagnationLimit;
        } else {
            // Longer diversification after unsuccessful intensification.
            this.maxDiversificationIterations = intensificationStagnationLimit * 3;
        }

        this.currentPhase = SearchPhase.DIVERSIFICATION;
        this.iterationsInCurrentPhase = 0;
        this.diversificationMemory.clear();
        this.sumOfMemoryCosts = 0.0;
    }

    /**
     * Transitions the search to the INTENSIFICATION phase.
     */
    private void switchToIntensification() {
        this.currentPhase = SearchPhase.INTENSIFICATION;
        this.iterationsInCurrentPhase = 0;
        // Record the best objective at the start of this new intensification attempt.
        this.bestObjectiveAtPhaseStart = bestObjectiveSoFar;
    }

    /**
     * Updates the memory of recent accepted solution costs during diversification.
     */
    private void updateMemory(double acceptedCost) {
        if (diversificationMemory.size() >= memorySize) {
            sumOfMemoryCosts -= diversificationMemory.removeFirst();
        }
        diversificationMemory.addLast(acceptedCost);
        sumOfMemoryCosts += acceptedCost;
    }

    /**
     * Adjusts the diversification threshold based on the quality of recently
     * accepted solutions and overall search progress.
     */
    private void adaptDiversificationThreshold() {
        if (diversificationMemory.isEmpty()) return;

        // Calculate the average quality of solutions accepted during diversification.
        double avgMemoryCost = sumOfMemoryCosts / diversificationMemory.size();

        // The new threshold is based on the gap between the average accepted cost and the best.
        // A larger gap implies the search is far away, requiring a larger threshold to escape.
        double adaptiveThreshold = (avgMemoryCost - bestObjectiveSoFar);

        // Globally decay the threshold over the search run to ensure eventual convergence.
        double progress = getSearchProgress();
        double maxAllowedThreshold = initialDiversificationThreshold -
                (initialDiversificationThreshold - minDiversificationThreshold) * progress;

        // Set the new threshold, ensuring it stays within logical bounds.
        this.diversificationThreshold = Math.max(minDiversificationThreshold, Math.min(adaptiveThreshold, maxAllowedThreshold));
    }

    /**
     * Calculates the fraction of the search budget that has been consumed.
     *
     * @return A value between 0.0 and 1.0 representing search progress.
     */
    private double getSearchProgress() {
        if (executionMaximumLimit <= 0) return 0.0;
        double progress;
        switch (stoppingCriterionType) {
            case Iteration:
                progress = (double) globalIterator / executionMaximumLimit;
                break;
            case Time:
                double elapsedSeconds = (System.nanoTime() - startTimeNano) / 1_000_000_000.0;
                progress = elapsedSeconds / executionMaximumLimit;
                break;
            default:
                progress = 0.0;
        }
        return Math.min(1.0, progress); // Clamp progress to [0, 1].
    }

    // --- Public Getters & Setters for Interface Compatibility ---

    /**
     * For compatibility, 'eta' represents the current diversification threshold.
     * A larger value indicates more lenient acceptance (more exploration).
     *
     * @return The current diversification threshold.
     */
    public double getEta() {
        return this.diversificationThreshold;
    }

    /**
     * Allows external modification of the diversification threshold ('eta').
     *
     * @param newThreshold The new threshold value to set.
     */
    public void setEta(double newThreshold) {
        this.diversificationThreshold = Math.max(0.0, newThreshold);
    }

    /**
     * Returns the effective objective function threshold for the next acceptance decision.
     *
     * @return The maximum objective value a new solution can have to be accepted.
     */
    public double getThresholdOF() {
        if (currentPhase == SearchPhase.INTENSIFICATION) {
            return lastAcceptedObjective;
        } else {
            return bestObjectiveSoFar + diversificationThreshold;
        }
    }

    public void setIdealFlow(double idealFlow) {
        // 空实现，具体逻辑根据需要添加
    }
}