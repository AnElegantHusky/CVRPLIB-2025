package DiversityControl;

import Data.Instance;
import SearchMethod.Config;
import SearchMethod.StoppingCriterionType;
import Solution.Solution;
import java.util.concurrent.ThreadLocalRandom;

/**
 * Implements a Threshold Accepting with Adaptive Patience (TAAP) mechanism.
 * This strategy uses a deterministic Threshold Accepting criterion, where a candidate
 * solution is accepted if its cost is not worse than the last accepted cost by more
 * than a dynamic threshold. This threshold adapts based on the search's progress:
 * it increases ("patience") during stagnation to allow more exploration and
 * decreases ("impatience") upon finding new best solutions to intensify the search.
 *
 * @author [Your Name/Team] - Refactored for enhanced performance
 */
public class AcceptanceCriterion {

    // --- Core State ---
    private double bestCostSoFar = Double.MAX_VALUE;
    private double previousAcceptedCost = Double.MAX_VALUE;

    // --- Threshold Accepting with Adaptive Patience (TAAP) Parameters ---
    /**
     * The dynamic acceptance threshold. A solution is accepted if:
     * candidateCost <= previousAcceptedCost + threshold.
     */
    private double threshold;
    private final double maxThreshold; // The upper bound for the threshold (from etaMax).
    private final double minThreshold; // The lower bound for the threshold (from etaMin).
    private final double thresholdDecayFactor = 0.98; // Factor for gradual threshold reduction.

    // --- Adaptation Control ---
    /**
     * "Patience" counter. Measures iterations since the last improvement.
     * When it reaches a limit, the threshold is increased to allow more diversification.
     */
    private int patienceCounter = 0;
    private final int patienceLimit; // Max patience before increasing threshold (from gamma).

    // --- Search Progress Tracking ---
    private int globalIterator = 0; // Total number of acceptance checks.

    /**
     * Constructs the acceptance criterion using the TAAP strategy.
     *
     * @param instance The CVRP problem instance (for context).
     * @param config The solver's configuration, providing all necessary parameters.
     * @param executionMaximumLimit The stopping limit (for context).
     */
    public AcceptanceCriterion(Instance instance, Config config, Double executionMaximumLimit) {
        // Repurpose etaMin/etaMax to define the bounds for the acceptance threshold.
        // A small initial threshold encourages early exploitation of the initial solution.
        this.minThreshold = config.getEtaMin();
        this.maxThreshold = config.getEtaMax();
        this.threshold = this.minThreshold;

        // Repurpose gamma to define the patience limit. After this many non-improving
        // iterations, the search is considered stagnated, triggering an adaptation.
        this.patienceLimit = config.getGamma();
    }

    /**
     * Determines whether to accept a new candidate solution based on the TAAP strategy.
     *
     * @param candidateSolution The solution to be evaluated.
     * @return {@code true} if the solution is accepted, {@code false} otherwise.
     */
    public boolean acceptSolution(Solution candidateSolution) {
        // Initialize the search state on the very first iteration.
        if (globalIterator == 0) {
            initializeSearch(candidateSolution.f);
        }

        double candidateCost = candidateSolution.f;
        boolean isAccepted = false;

        // --- Core TAAP Acceptance Logic ---
        // 1. Aspiration Criterion: Always accept a globally improving solution.
        if (candidateCost < bestCostSoFar) {
            isAccepted = true;
            bestCostSoFar = candidateCost;

            // Finding a new best solution shows impatience: reset the counter and
            // significantly reduce the threshold to exploit the promising new area.
            patienceCounter = 0;
            threshold = Math.max(minThreshold, threshold * 0.5);
        }
        // 2. Threshold Accepting: Accept non-improving solutions if they are "close enough"
        //    to the last accepted solution, as defined by the current dynamic threshold.
        //    This is a deterministic check, unlike the probabilistic SA.
        else if (candidateCost <= previousAcceptedCost + threshold) {
            isAccepted = true;
        }

        // --- Update State and Parameters ---
        if (isAccepted) {
            previousAcceptedCost = candidateCost;
        } else {
            // If the solution is not accepted, it contributes to stagnation.
            patienceCounter++;
        }

        globalIterator++;
        updateParameters(); // Adapt the threshold based on patience.

        return isAccepted;
    }

    /**
     * Initializes the cost trackers with the first solution's cost.
     *
     * @param initialCost The cost of the very first solution.
     */
    private void initializeSearch(double initialCost) {
        this.bestCostSoFar = initialCost;
        this.previousAcceptedCost = initialCost;
    }

    /**
     * Dynamically updates the acceptance threshold based on search progress.
     */
    private void updateParameters() {
        // 1. Check for Stagnation (Patience Limit Reached)
        if (patienceCounter >= patienceLimit) {
            // If the search is stuck, increase the threshold to be more lenient and
            // accept worse solutions, thereby encouraging exploration to escape local optima.
            // A multiplicative increase allows for rapid escape from deep valleys.
            threshold = Math.min(maxThreshold, threshold * 1.25);
            patienceCounter = 0; // Reset patience after taking action.
        } else {
            // 2. Gradual Cooling
            // In every iteration where patience has not run out, slightly decrease
            // the threshold. This promotes a general trend towards intensification
            // as the search progresses, tightening the acceptance criteria over time.
            threshold *= thresholdDecayFactor;
        }

        // 3. Enforce Bounds
        // Ensure the threshold always stays within its predefined min/max limits.
        threshold = Math.max(minThreshold, threshold);
    }

    // --- Public Getters & Setters for Interface Compatibility ---

    /**
     * Returns the current acceptance threshold, analogous to the original 'eta' parameter.
     *
     * @return The current acceptance threshold.
     */
    public double getEta() {
        return this.threshold;
    }

    /**
     * Returns the current acceptance cost limit, defined by the Threshold Accepting criterion.
     * This is the cost of the last accepted solution plus the current threshold.
     *
     * @return The current acceptance threshold value.
     */
    public double getThresholdOF() {
        return this.previousAcceptedCost + this.threshold;
    }

    /**
     * Sets the current acceptance threshold (analogous to 'eta').
     *
     * @param eta The new threshold value to set. It will be clamped within bounds.
     */
    public void setEta(double eta) {
        this.threshold = Math.max(this.minThreshold, Math.min(eta, this.maxThreshold));
    }

    /**
     * Returns the maximum acceptance threshold (etaMax), which is the upper bound for the threshold.
     *
     * @return The maximum threshold value.
     */
    public double getEtaMax() {
        return this.maxThreshold;
    }
}