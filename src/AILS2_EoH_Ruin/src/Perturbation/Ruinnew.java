package Perturbation;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

import Data.Instance;
import DiversityControl.OmegaAdjustment;
import Improvement.IntraLocalSearch;
import SearchMethod.Config;
import Solution.Node;
import Solution.Solution;

// Ruinnew: Implements a Route-Based Split Ruin strategy
public class Ruinnew extends Perturbation
{
    public Ruinnew(Instance instance, Config config,
                  HashMap<String, OmegaAdjustment> omegasetup, IntraLocalSearch intraLocalSearch)
    {
        super(instance, config, omegasetup, intraLocalSearch);
        this.perturbationType = PerturbationType.Ruinnew;
    }

    @Override
    public void applyPerturbation(Solution s)
    {
        // 1. Initialize solution references from the parent class
        setSolution(s);

        // 2. Select a random "seed" node that belongs to a route
        Node seedNode = null;
        int attempts = 0;
        while (seedNode == null || !seedNode.nodeBelong) {
            seedNode = solution[rand.nextInt(solution.length)];
            attempts++;
            if (attempts > solution.length * 2) return; // Safety exit if solution is empty
        }

        // 3. Collect neighbors based on Route Adjacency (Predecessors and Successors)
        List<Node> targetNodes = new ArrayList<>();
        targetNodes.add(seedNode);

        Node backwardPointer = seedNode.prev;
        Node forwardPointer = seedNode.next;
        boolean expandForward = true;

        while (targetNodes.size() < omega) {
            boolean added = false;
            if (expandForward) {
                if (forwardPointer != null && forwardPointer.nodeBelong && !targetNodes.contains(forwardPointer)) {
                    targetNodes.add(forwardPointer);
                    forwardPointer = forwardPointer.next;
                    added = true;
                }
            } else {
                if (backwardPointer != null && backwardPointer.nodeBelong && !targetNodes.contains(backwardPointer)) {
                    targetNodes.add(backwardPointer);
                    backwardPointer = backwardPointer.prev;
                    added = true;
                }
            }

            if (!added) {
                if ((forwardPointer == null || !forwardPointer.nodeBelong) &&
                    (backwardPointer == null || !backwardPointer.nodeBelong)) {
                    break;
                }
            }

            expandForward = !expandForward;
        }

        // 4. Fallback: If the route was shorter than omega, fill remainder with random nodes
        while (targetNodes.size() < omega) {
            Node randomNode = solution[rand.nextInt(solution.length)];
            if (randomNode.nodeBelong && !targetNodes.contains(randomNode)) {
                targetNodes.add(randomNode);
            }
        }

        // 5. Remove the selected nodes
        for (Node node : targetNodes) {
            if (countCandidates >= omega) break;

            node.prevOld = node.prev;
            node.nextOld = node.next;

            candidates[countCandidates] = node;
            countCandidates++;
            f += node.route.remove(node);
        }

        // 6. Set re-insertion order (Random or predefined logic in parent)
        setOrder();

        // 7. Re-insert nodes using the configured Repair operator (e.g., Greedy/Regret)
        addCandidates();

        // 8. Finalize changes
        assignSolution(s);
    }
}