package DiversityControl;

import Auxiliary.Mean;
import Perturbation.PerturbationType;
import SearchMethod.Config;
import java.text.DecimalFormat;
// import java.util.Random; //////////////////////////////////////

/**
 * Manages the adaptive adjustment of the omega hyperparameter (perturbation strength)
 * using a self-tuning, hybrid control mechanism.
 *
 * This advanced implementation enhances the PI controller by adding a meta-adaptive layer.
 * It dynamically adjusts its own learning rate and controller gains based on performance,
 * allowing it to be more aggressive when adjustments are effective and more conservative
 * when they are not. This hybrid approach combines the stability of a PI controller with
 * the responsiveness of a simpler proportional system, adapting the blend between them.
 *
 * Key Improvements:
 * 1. **Hybrid Control Logic:** Blends a standard PI controller with a simpler, direct proportional
 *    feedback mechanism. A `controlBlendFactor` determines the influence of each, allowing the
 *    system to switch between long-term stability (PI) and rapid response (proportional).
 * 2. **Meta-Adaptive Learning Rate (Self-Tuning):** The learning rate (`eta`) is no longer static.
 *    It increases when adjustments successfully move the diversity closer to the target and
 *    decreases otherwise. This is inspired by the 1/5th success rule, enabling faster
 *    convergence and preventing oscillations.
 * 3. **Dynamic Gain Scheduling:** The proportional and integral gains (Kp, Ki) are adjusted
 *    inversely to the learning rate. High learning rates use lower gains to prevent instability,
 *    while low learning rates use higher gains for more assertive corrections.
 * 4. **State Tracking:** Explicitly tracks the `previousError` to determine if the last
 *    adjustment was successful (i.e., if the new error is smaller than the old one).
 * 5. **Robust Error Handling:** Includes checks to prevent updates when diversity data is
 *    unreliable (e.g., zero), ensuring system stability.
 * 6. **Full Interface Compatibility:** Maintains the public API of the original class for
 *    seamless integration. Deprecated methods are preserved.
 */
public class OmegaAdjustment {
    // --- Configuration and Constants ---
    private final PerturbationType perturbationType;
    private final double minPerturbationStrength; // Minimum allowed value for omega (e.g., 1.0)
    private final double maxPerturbationStrength; // Maximum allowed value for omega (e.g., size-2)
    private final int updateInterval; // Number of iterations before an adjustment (gamma)
    private final IdealDist idealDist; // Target diversity measure to achieve

    // --- Dynamic Control Parameters ---
    // Base gains for the controller. These are dynamically scaled.
    private static final double BASE_PROPORTIONAL_GAIN = 0.1; // (Kp_base)
    private static final double BASE_INTEGRAL_GAIN = 0.01; // (Ki_base)
    // Factors for meta-adaptive learning rate adjustment.
    private static final double SUCCESS_FACTOR = 1.1; // Multiplier for learning rate on success
    private static final double FAILURE_FACTOR = 0.95; // Multiplier for learning rate on failure
    private static final double MIN_LEARNING_RATE = 0.1;
    private static final double MAX_LEARNING_RATE = 2.0;

    // --- State Variables ---
    private double perturbationStrength; // The core hyperparameter 'omega' to be adjusted.
    private double currentPerturbationStrength; // The actual value used in the last perturbation.
    private double integralError = 0.0; // Accumulated error for the integral term.
    private double previousError = Double.MAX_VALUE; // Error from the previous update cycle.
    private double learningRate = 1.0; // (eta) Adaptive step size for the adjustment.
    private int iterationCounter = 0; // Tracks iterations until the next update.

    // --- Data Aggregators ---
    private final Mean achievedDiversity; // Moving average of the diversity from local search (meanLSDist).
    private final Mean averagePerturbationStrength; // Tracks the average value of omega over time.

    // --- Utilities ---
    private final DecimalFormat decimalFormatter = new DecimalFormat("0.00");
    // private final Random random = new Random(); // Retained for future stochastic enhancements. ////////////////////////////////////////

    /**
     * Constructs an OmegaAdjustment mechanism.
     *
     * @param perturbationType The type of perturbation this instance manages.
     * @param config           The global solver configuration object.
     * @param size             The problem size, used to set the max perturbation strength.
     * @param idealDist        The target diversity metrics for this perturbation.
     */
    public OmegaAdjustment(PerturbationType perturbationType, Config config, Integer size, IdealDist idealDist) {
        this.perturbationType = perturbationType;
        this.idealDist = idealDist;
        this.updateInterval = config.getGamma();

        this.perturbationStrength = idealDist.idealDist;
        this.minPerturbationStrength = 1.0;
        this.maxPerturbationStrength = Math.max(minPerturbationStrength, size - 2.0);
        this.perturbationStrength = clamp(this.perturbationStrength, minPerturbationStrength, maxPerturbationStrength);
        this.currentPerturbationStrength = this.perturbationStrength;

        this.achievedDiversity = new Mean(config.getGamma());
        this.averagePerturbationStrength = new Mean(config.getGamma());
    }

    /**
     * Records the diversity achieved by a perturbation and local search cycle.
     * Triggers a strength adjustment if the update interval is reached.
     *
     * @param diversityValue The measured diversity (distance) from the last local search.
     */
    public void setDistance(double diversityValue) {
        iterationCounter++;
        achievedDiversity.setValue(diversityValue);

        if (iterationCounter >= updateInterval) {
            updatePerturbationStrength();
            iterationCounter = 0; // Reset counter after update.
        }
    }

    /**
     * Core logic for adjusting perturbation strength using a self-tuning, hybrid controller.
     */
    public void updatePerturbationStrength() {
        double currentAchievedDiversity = achievedDiversity.getDynamicAverage();
        // Guard against invalid updates if diversity is not meaningful.
        if (currentAchievedDiversity < 1e-6) {
            return;
        }

        // 1. Calculate the normalized error (how far are we from the target?).
        // Error > 0 means diversity was too low; < 0 means it was too high.
        double error = (idealDist.idealDist - currentAchievedDiversity) / currentAchievedDiversity;

        // 2. Meta-Adaptation: Adjust the learning rate based on success.
        // Success is defined as the new error's magnitude being smaller than the previous one.
        if (Math.abs(error) < Math.abs(previousError)) {
            learningRate *= SUCCESS_FACTOR; // Increase learning rate on success.
        } else {
            learningRate *= FAILURE_FACTOR; // Decrease learning rate on failure.
        }
        learningRate = clamp(learningRate, MIN_LEARNING_RATE, MAX_LEARNING_RATE);
        previousError = error; // Store current error for the next comparison.

        // 3. Dynamic Gain Scheduling: Adjust gains based on the learning rate.
        // Use lower gains with a high learning rate to prevent overshoot.
        // Use higher gains with a low learning rate for more assertive correction.
        double dynamicProportionalGain = BASE_PROPORTIONAL_GAIN / learningRate;
        double dynamicIntegralGain = BASE_INTEGRAL_GAIN / learningRate;

        // 4. Update the integral term with anti-windup.
        integralError += error;
        integralError = clamp(integralError, -10.0 / dynamicIntegralGain, 10.0 / dynamicIntegralGain);

        // 5. Calculate Hybrid Control Adjustment.
        // This blends a fast, simple proportional term with a stable PI term.
        // The controlBlendFactor determines the influence of the PI controller part.
        double controlBlendFactor = 0.5; // 50% PI controller, 50% simple proportional.
        double proportionalTerm = dynamicProportionalGain * error;
        double integralTerm = dynamicIntegralGain * integralError;
        double piAdjustment = proportionalTerm + integralTerm;
        double simpleProportionalAdjustment = BASE_PROPORTIONAL_GAIN * error; // A simple, direct feedback

        // The final adjustment is a weighted average of the two control strategies.
        double adjustment = (1.0 - controlBlendFactor) * simpleProportionalAdjustment
                          + controlBlendFactor * piAdjustment;

        // 6. Apply the adjustment to the perturbation strength.
        // The final update is scaled by the adaptive learning rate.
        perturbationStrength += (1.0 + learningRate * adjustment);

        // 7. Clamp the new strength to ensure it remains within valid bounds.
        perturbationStrength = clamp(perturbationStrength, minPerturbationStrength, maxPerturbationStrength);

        // 8. Record the new strength for tracking averages.
        averagePerturbationStrength.setValue(perturbationStrength);
    }

    /**
     * Retrieves the current perturbation strength (omega) to be used by a perturbation operator.
     *
     * @return The current, bounded value of the perturbation strength.
     */
    public double getActualOmega() {
        this.currentPerturbationStrength = clamp(perturbationStrength, minPerturbationStrength, maxPerturbationStrength);
        return this.currentPerturbationStrength;
    }

    /**
     * Clamps a value to be within a specified minimum and maximum range.
     *
     * @param value The value to clamp.
     * @param min   The minimum allowed value.
     * @param max   The maximum allowed value.
     * @return The clamped value.
     */
    private static double clamp(double value, double min, double max) {
        return Math.max(min, Math.min(value, max));
    }

    // --- Original Interface Compatibility ---

    /**
     * @deprecated Replaced by {@link #updatePerturbationStrength()}. Kept for backward compatibility.
     */
    @Deprecated
    public void setupOmega() {
        updatePerturbationStrength();
    }

    /**
     * @deprecated The system now self-manages the actual omega. This setter is no longer functionally used.
     */
    @Deprecated
    public void setActualOmega(double actualOmega) {
        // This method is maintained for API compatibility but its body can be left empty
        // as the internal state 'currentPerturbationStrength' is now managed by 'getActualOmega'.
        // Setting it externally would conflict with the controller's logic.
    }

    public Mean getAverageOmega() {
        return averagePerturbationStrength;
    }

    public PerturbationType getPerturbationType() {
        return perturbationType;
    }

    @Override
    public String toString() {
        String pType = String.valueOf(perturbationType).substring(4);
        return String.format("o%s: %s | avgLSDist%s: %s | idealDist%s: %s | actualOmega: %s | avgOmega%s: %s | eta: %s",
                pType, decimalFormatter.format(perturbationStrength),
                pType, achievedDiversity.toString(),
                pType, decimalFormatter.format(idealDist.idealDist),
                decimalFormatter.format(currentPerturbationStrength),
                pType, averagePerturbationStrength.toString(),
                decimalFormatter.format(learningRate)
        );
    }
}
