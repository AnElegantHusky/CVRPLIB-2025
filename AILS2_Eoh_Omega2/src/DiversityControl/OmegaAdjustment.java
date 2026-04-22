package DiversityControl;

import Auxiliary.Mean;
import Perturbation.PerturbationType;
import SearchMethod.Config;

import java.text.DecimalFormat;
import java.util.Objects;
import java.util.Random;

/**
 * Implements a state-based adaptive mechanism for the omega hyperparameter in CVRP perturbation heuristics.
 * This class uses a finite-state machine to switch between different adjustment strategies (Aggressive, Stable, Corrective)
 * based on the system's performance, enabling both rapid exploration and fine-tuned stability. This approach
 * avoids the one-size-fits-all parameter tuning of traditional controllers, adapting its behavior to the current search phase.
 * 
 * @version 3.0
 * @since 2024-05-22
 */
public class OmegaAdjustment {
    
    // --- Core Configuration ---
    private final double omegaMin;
    private final double omegaMax;
    private final int updateInterval;
    private final IdealDist idealDist;
    private final PerturbationType perturbationType;
    
    // --- State Machine ---
    private enum ControlState { AGGRESSIVE, STABLE, CORRECTIVE }
    private ControlState currentState = ControlState.STABLE; // Start in a balanced state.
    
    // --- State-Specific Control Parameters ---
    // AGGRESSIVE: For large errors, move omega quickly towards the target.
    private static final double AGGRESSIVE_ADJUSTMENT_FACTOR = 0.5;
    // STABLE: For small errors, makes fine-tuned, smooth adjustments using a PI-like controller.
    private static final double STABLE_PROPORTIONAL_GAIN = 0.08;
    private static final double STABLE_INTERNAL_GAIN = 0.01;
    // CORRECTIVE: For when observed distance is zero, provides a controlled boost to escape stagnation.
    private static final double CORRECTIVE_BOOST_FACTOR = 1.10;
    
    // --- State Transition Thresholds ---
    // Define the 'server zone' where the STABLE state is active.
    // If |error| / idealDist > this value, switch to AGGRESSIVE.
    private static final double AGGRESSIVE_THRESHOLD_RATIO = 0.25; // 25% error margin
    
    // --- Internal State Variables ---
    private double omega;
    private double integralError = 0.0;
    private int iterationsSinceLastUpdate = 0;
    
    // --- Monitoring & Logging ---
    private final Mean meanObservedDistance;
    private final Mean averageOmega;
    private static final DecimalFormat DECIMAL_FORMAT = new DecimalFormat("0.00");
    private final Random rand = new Random(); // Kept for potential future stochastic extensions.
    
    /**
     * Construct the state-based OmegaAdjustment instance.
     *
     * @param perturbationType The type of perturbation this adjuster manages.
     * @param config The solver's configuration object.
     * @param problemSize The size of the problem (e.g., number of customers).
     * @param idealDist A wrapper object containing the target perturbation distance.
     */
    public OmegaAdjustment(PerturbationType perturbationType, Config config, Integer problemSize, IdealDist idealDist) {
        // --- Input Validation ---
        this.perturbationType = Objects.requireNonNull(perturbationType, "PerturbationType cannot be null.");
        this.idealDist = Objects.requireNonNull(idealDist, "IdealDist cannot be null.");
        Objects.requireNonNull(config, "Config cannot be null.");
        Objects.requireNonNull(problemSize, "Problem size cannot be null.");
        if (problemSize < 2) {
            throw new IllegalArgumentException("Problem size must be at least 2.");
        }
        
        // --- Initialization ---
        this.updateInterval = config.getGamma();
        this.omegaMin = 1.0;
        this.omegaMax = Math.max(omegaMin, problemSize - 2.0);
        
        // Start omega at a reasonable value, clamped to its valid range.
        this.omega = clamp(idealDist.idealDist, omegaMin, omegaMax);
        
        // Initialize monitoring tools.
        this.meanObservedDistance = new Mean(config.getGamma());
        this.averageOmega = new Mean(config.getGamma());
    }
    
    /**
     * Records an observed perturbation distance and triggers an omega update if the interval is met.
     * This is the main entry point for the class during the search process.
     * @param observedDistance The actual distance/impact of the last perturbation.
     */
    public void setDistance(double observedDistance) {
        meanObservedDistance.setValue(observedDistance);
        iterationsSinceLastUpdate++;
        if (iterationsSinceLastUpdate >= updateInterval) {
            updateOmega();
            iterationsSinceLastUpdate = 0; // Reset counter after update.
        }
    }
    
    /**
     * Core state machine logic for updating omega. It first determines the current state
     * based on performance and then delegates the adjustment calculation to a state-specific handler.
     */
    private void updateOmega() {
        double currentAverageDistance = meanObservedDistance.getDynamicAverage();
        double targetDistance = idealDist.idealDist;
        double error = targetDistance - currentAverageDistance;
        
        // 1. Determine the current control state.
        updateControlState(currentAverageDistance, error, targetDistance);
        
        // 2. Execute the adjustment logic for the current state.
        switch (currentState) {
            case AGGRESSIVE:
                performAggressiveAdjustment(error);
                break;
            case STABLE:
                performStableAdjustment(error);
                break;
            case CORRECTIVE:
                performCorrectiveAdjustment();
                break;
        }
        
        // 3. Ensure omega remains within bounds and record it for monitoring.
        this.omega = clamp(omega, omegaMin, omegaMax);
        averageOmega.setValue(omega);
    }
    
    /**
     * Transitions the state machine based on the current error and observed distance.
     * @param avgDist The current average observed distance.
     * @param error The difference between the target and average distance.
     * @param targetDist The target ideal distance.
     */
    private void updateControlState(double avgDist, double error, double targetDist) {
        if (avgDist < 1e-9) {
            // If there's no observed distance, we are stuck. Enter corrective state.
            currentState = ControlState.CORRECTIVE;
        } else if (Math.abs(error) / targetDist > AGGRESSIVE_THRESHOLD_RATIO) {
            // If the relative error is large, an aggressive correction is needed.
            currentState = ControlState.AGGRESSIVE;
            integralError = 0; // Reset integral term when making large jumps.
        } else {
            // If the error is within a tolerable range, use the stable PI controller.
            currentState = ControlState.STABLE;
        }
    }
    
    /**
     * State Handler: Rapidly adjusts omega when the error is large.
     * It uses a simple proportional control with a high gain.
     * @param error The current error (target - observed).
     */
    private void performAggressiveAdjustment(double error) {
        double adjustment = error * AGGRESSIVE_ADJUSTMENT_FACTOR;
        this.omega += adjustment;
    }
    
    /**
     * State Handler: Fine-tunes omega using a PI controller when the error is small.
     * This provides smooth convergence and stability near the target.
     * @param error The current error (target - observed).
     */
    private void performStableAdjustment(double error) {
        // Update the integral error (accumulated past error).
        integralError += error;
        
        // Anti-windup: Clamp the integral term to prevent it from growing excessively.
        double integralMax = omegaMax / 2.0; // Heuristic limit
        integralError = clamp(integralError, -integralMax, integralMax);
        
        // Calculate adjustment using the PI formula for the stable state.
        double proportionalTerm = STABLE_PROPORTIONAL_GAIN * error;
        double integralTerm = STABLE_INTERNAL_GAIN * integralError;
        this.omega += proportionalTerm + integralTerm;
    }
    
    /**
     * State Handler: Applies a multiplicative boost to omega to escape stagnation
     * when the observed perturbation distance is zero.
     */
    private void performCorrectiveAdjustment() {
        this.omega *= CORRECTIVE_BOOST_FACTOR;
        integralError = 0; // Reset integral term after a corrective jump.
    }
    
    // --- Helper Methods & Getters ---
    
    /**
     * A utility method to constrain a value within a given range [min, max].
     * @param value The value to clamp.
     * @param min The minimum allowed value.
     * @param max The maximum allowed value.
     * @return The clamped value.
     */
    private static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(value, max));
    }
    
    /**
     * Returns the current omega value for use in the perturbation algorithm.
     * @return The current, clamped value of omega.
     */
    public double getActualOmega() {
        return this.omega;
    }
    
    public Mean getAverageOmega() {
        return averageOmega;
    }
    
    public PerturbationType getPerturbationType() {
        return perturbationType;
    }
    
    // --- Compatibility Methods ---
    
    /**
     * Sets the internal omega value directly. Provided for API compatibility.
     * The value is clamped to ensure it remains valid.
     * @param actualOmega The new value for omega.
     */
    public void setActualOmega(double actualOmega) {
        this.omega = clamp(actualOmega, omegaMin, omegaMax);
        integralError = 0; // Reset controller state after external override.
    }
    
    @Override
    public String toString() {
        String typeSuffix = String.valueOf(perturbationType).substring(0, 5);
        String stateIndicator = currentState.toString().substring(0, 1); // A, S, C
        return String.format(
            "-%s: %s (%s) | avgDist: %s | idealDist: %s | avg:- %s",
            typeSuffix, DECIMAL_FORMAT.format(this.omega), stateIndicator,
            meanObservedDistance.toString(),
            DECIMAL_FORMAT.format(idealDist.idealDist),
            averageOmega.toString()
        );
    }
}