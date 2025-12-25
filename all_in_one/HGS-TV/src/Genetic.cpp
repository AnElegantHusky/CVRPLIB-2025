#include "Genetic.h"

#include <chrono> // for wall-clock time when writing to shared DB

#include <chrono>
#include <ctime>
#include <iostream>
#include <limits>
#include <random>

namespace genvrp {
    void Genetic::injectInitialRoutes(const std::vector<std::vector<int>>& routes) {
        const int nbVehicles = params.data.nbVehicles;
        const int nbClients = params.data.nbClients;

        if(routes.empty()) {
            return;
        }

        auto initIndiv = std::make_unique<Individual>(&params);

        // Reset routes to match the problem definition.
        initIndiv->routes.assign(nbVehicles, {});

        // Copy routes from the provided solution, truncating if too many.
        for(std::size_t r = 0; r < routes.size() && static_cast<int>(r) < nbVehicles; ++r) {
            initIndiv->routes[static_cast<int>(r)] = routes[r];
        }

        // Rebuild predecessor/successor information.
        initIndiv->successors.assign(nbClients + 1, 0);
        initIndiv->predecessors.assign(nbClients + 1, 0);

        for(const auto& route : initIndiv->routes) {
            if(route.empty()) {
                continue;
            }

            initIndiv->predecessors[route.front()] = 0;

            for(std::size_t i = 1; i < route.size(); ++i) {
                const int prev = route[i - 1];
                const int curr = route[i];
                initIndiv->successors[prev] = curr;
                initIndiv->predecessors[curr] = prev;
            }

            initIndiv->successors[route.back()] = 0;
        }

        // Rebuild a compatible giant tour by concatenating all routes.
        std::vector<int> tour;
        tour.reserve(nbClients);
        for(const auto& route : initIndiv->routes) {
            for(int cust : route) {
                tour.push_back(cust);
            }
        }

        if(static_cast<int>(tour.size()) == nbClients) {
            initIndiv->giantTour = std::move(tour);
        }

        // Evaluate and optionally improve the injected solution so that
        // it is consistent with the current penalty parameters.
        initIndiv->evaluateCompleteCost();
        localSearch.run(initIndiv.get(), params.ga.penaltyCapacity, params.ga.penaltyDuration);
        initIndiv->evaluateCompleteCost();

        addInitialIndividual(std::move(initIndiv));
    }
    std::optional<Individual> Genetic::run(const SolverStatus& initialStatus) {
        using namespace std::chrono;

        // Reset the elapsed time.
        elapsed = 0.0;

#ifndef BATCH_MODE
        std::cout << initialStatus.outPrefix << "[Algorithm] Starting the genetic algorithm.\n";
#endif

        // Cannot start with negative elapsed time!
        assert(initialStatus.initialElapsedTime >= 0);

		// Number of consecutive iterations without improvement.
        int nbIterNonProd = 1;

        // Current iteration number.
        int nbIter = 0;

        // CPU time start of the algorithm (using std::clock for CPU time).
        const std::clock_t startTime = std::clock();
        std::clock_t lastDecoTime = startTime;

        // 上次向共享 DB 推送解时的“协同时间”（秒）。
        // 单位与 runningTimeForDb 一致：优先使用 wall-clock - globalStartTimeSec，若无则退回 CPU elapsed。
        double lastDbUpdateTime = 0.0;
        // 自上次 DB 更新以来，是否出现过新的最优解（用于触发按需写库，与 FILO2 / AILS2 对齐）。
        bool improvedSinceLastDbUpdate = false;
        // 保存找到改进解时的最优解副本（类似 FILO2 的 record_solution），确保写入数据库时使用已确认改进的解
        std::optional<Individual> recordBestSolution;

		// While the iteration termination criteria are not met:
        while(nbIter < params.ga.maxIter && nbIterNonProd < params.ga.maxIterNonProd) {
            // Check if we are in timeout (using CPU time):
            const std::clock_t currentTime = std::clock();
            elapsed = static_cast<double>(currentTime - startTime) / CLOCKS_PER_SEC;

			// In this case, exit.
            if(elapsed > params.ga.timeoutSec - initialStatus.initialElapsedTime) {
                break;
            }

            // Generate a new individual (offspring) via cross-over.
            auto offspring = crossoverOX(*population.getBinaryTournament(), *population.getBinaryTournament());

            // Run local search on the new individual.
            localSearch.run(&offspring, params.ga.penaltyCapacity, params.ga.penaltyDuration);

			// Update the frequency table, if it is being used.
            if(params.vfreq) {
                updateCustomerFrequencyMatrix(offspring);
            }

            // Update the arc frequency matrix, if it is being used.
            if(params.afreq) {
                updateArcFrequencyMatrix(offspring);
            }

            // Update the path frequency matrix, if it is being used.
            if(params.pfreq) {
                updatePathFrequencyMatrix(offspring);
            }

            // Add the new individual to the population.
            bool isNewBest = population.addIndividual(&offspring, true);

			// If the individual is unfeasible, try to repair it with
            // a certain probability.
            if(!offspring.isFeasible && std::rand() % 2 == 0) {
                localSearch.run(&offspring, params.ga.penaltyCapacity * 10., params.ga.penaltyDuration * 10.);

				// If the repair was succesfull, also add the repaired
                // individual to the population.
                if(offspring.isFeasible)
                    isNewBest = (population.addIndividual(&offspring, false) || isNewBest);
            }

            
            // If the best solution was improved by the new individual...
            if(isNewBest) {
                // Reset the counter
                nbIterNonProd = 1;

                // 标记：自上次 DB 更新以来出现过改进
                improvedSinceLastDbUpdate = true;

                // 立即保存当前最优解的副本（类似 FILO2 的 record_solution），确保写入数据库时使用已确认改进的解
                // 这样可以避免在找到改进解和写入数据库之间，bestSolutionOverall 被更新为更差的解
                std::optional<const Individual*> currentBest = population.getBestFound();
                if(currentBest && currentBest.value()->isFeasible) {
                    recordBestSolution = *currentBest.value();
                }

                // Update the stats about new best solutions.
                if(params.stats.recordBestSolutionUpdates) {
                    const std::clock_t timeAtUpdate = std::clock();
                    const double elapsedAtUpdate = static_cast<double>(timeAtUpdate - startTime) / CLOCKS_PER_SEC;

                    params.stats.newBestIndividuals.push_back(
                        {Params::RunStats::NewBestSource::MainGenetic, offspring.cost.penalizedCost, elapsedAtUpdate});
                }
            } else {
                nbIterNonProd++;
            }

            // 与 FILO2 / AILS2 一致：仅在“出现过改进”且间隔超过 updateInterval 时，向共享 DB 推送当前最优解（只在主问题层级）。
            if(!params.pathToSharedDb.empty()
               && initialStatus.recursionLevel == 0u
               && params.dbUpdateIntervalSec > 0.0
               && improvedSinceLastDbUpdate) {

                // 先计算“协同时间轴”上的当前运行时间
                double runningTimeForDb = elapsed;
                if(params.globalStartTimeSec > 0.0) {
                    const auto now = std::chrono::system_clock::now();
                    const double nowSec = std::chrono::duration<double>(now.time_since_epoch()).count();
                    runningTimeForDb = nowSec - params.globalStartTimeSec;
                    if(runningTimeForDb < 0.0) {
                        runningTimeForDb = 0.0;
                    }
                }

                // 若距离上次 DB 写入的时间不足 updateInterval，则暂不写入
                if((runningTimeForDb - lastDbUpdateTime) >= params.dbUpdateIntervalSec) {
                    // 使用已保存的改进解（类似 FILO2 的 record_solution），而不是重新获取 bestSolutionOverall
                    // 这样可以确保写入数据库的解是已确认改进的解，避免 bestSolutionOverall 被更新为更差的解
                    if(recordBestSolution && recordBestSolution.value().isFeasible) {
                        HgsDbConfig cfg{params.pathToSharedDb, "HGS-TV"};
                        saveBestIndividualToDb(cfg, recordBestSolution.value(), runningTimeForDb);
                        lastDbUpdateTime = runningTimeForDb;
                        improvedSinceLastDbUpdate = false;
                        // 清空已保存的解，等待下次改进
                        recordBestSolution.reset();
                    }
                }
            }

            // Adjust the penalty multipliers.
            if(nbIter % params.ga.adjMultiplierIters == 0) {
                population.managePenalties();
            }

// Print info on the current state of the search.
#ifndef BATCH_MODE
            if(nbIter % params.ga.outputIters == 0) {
                population.printState(nbIter, nbIterNonProd, initialStatus.outPrefix);
            }
#endif

            // Decompose the problem.
            if(decomposition && nbIter > 0 && nbIter % params.deco.decompositionIters == 0) {
#ifndef BATCH_MODE
                std::cout << initialStatus.outPrefix << "[Algorithm] Attempting decomposition.\n";
#endif

                // If we are in the master problem, record its runtime.
                if(initialStatus.recursionLevel == 0u) {
                    const std::clock_t decoTime = std::clock();
                    const double mpTimeSinceDeco = static_cast<double>(decoTime - lastDecoTime) / CLOCKS_PER_SEC;
                    params.stats.mpTime += mpTimeSinceDeco;
                    params.stats.nMpDecompositions += 1u;
                }

                // Pass the solver status made of the current elapsed time
                // and the recursion level, which is the current recursion
                // level, increased by 1.
                (*decomposition)(population, SolverStatus{elapsed, initialStatus.recursionLevel + 1u});

                lastDecoTime = std::clock();
            }

            // If we reached the termination criterion in the main problem but there is some time left, I suggest restarting the algorithm to profit from the remaining time
            if(initialStatus.recursionLevel == 0u && (nbIter == params.ga.maxIter || nbIterNonProd == params.ga.maxIterNonProd)) {
                population.restart();
                nbIterNonProd = 1;
            }

			// Increase the current iteration number.
            ++nbIter;
        }

        // Calculate the elapsed CPU time.
        const std::clock_t finalTime = std::clock();
        elapsed = static_cast<double>(finalTime - startTime) / CLOCKS_PER_SEC;

        // Because it gets rounded up, check it is not more than the timeout.
        elapsed = std::min(elapsed, params.ga.timeoutSec);

        // If we are in the masterproblem, record its parameters.
        if(initialStatus.recursionLevel == 0u) {
            params.stats.mpTime += static_cast<double>(finalTime - lastDecoTime) / CLOCKS_PER_SEC;
            params.stats.nMpIterations = nbIter;
        }

        // If we are in a subproblem, record its parameters.
        if(initialStatus.recursionLevel > 0u) {
            params.stats.spTime = elapsed;
            params.stats.nSpIterations = nbIter;
        }

#ifndef BATCH_MODE
        std::cout << initialStatus.outPrefix << "[Algorithm] Recursion level: " << initialStatus.recursionLevel << "\n";
        std::cout << initialStatus.outPrefix << "[Algorithm] Time elapsed: " << elapsed << " seconds\n";
        std::cout << initialStatus.outPrefix << "[Algorithm] Number of iterations: " << nbIter << "\n";
#endif

        // Get the best feasible individual, if any.
        std::optional<const Individual*> bestIndiv = population.getBestFound();
        if(!bestIndiv) {
            // Otherwise, get the best infeasible one, if any.
            bestIndiv = population.getBestInfeasible();
        }
        if(!bestIndiv) {
            // No feasible and no infeasible individuals found.
            return std::nullopt;
        }

        // Return a copy of the best individual.
        return **bestIndiv;
    }

    Individual Genetic::crossoverOX(const Individual& parent1, const Individual& parent2) {
        // We initialize a frequency table to track the customers which have been already inserted.
        auto freqClient = std::vector<bool>(params.data.nbClients + 1, false);

        // We pick the beginning and end of the crossover zone.
        int start = std::rand() % params.data.nbClients;
        int end = std::rand() % params.data.nbClients;

        // Avoid that start and end coincide by accident.
        while(end == start && params.data.nbClients > 1) {
            end = std::rand() % params.data.nbClients;
        }

        // Create the resulting individual.
        Individual result{&params};

        int j = start;
        // We keep the elements from "start" to "end".
        while((j % params.data.nbClients) != ((end + 1) % params.data.nbClients)) {
            result.giantTour[j % params.data.nbClients] = parent1.giantTour[j % params.data.nbClients];
            freqClient[result.giantTour[j % params.data.nbClients]] = true;
            j++;
        }

        // We fill the rest of the elements in the order of the second parent.
        for(int i = 1; i <= params.data.nbClients; i++) {
            int index = parent2.giantTour[(end + i) % params.data.nbClients];
            if(freqClient[index] == false) {
                result.giantTour[j % params.data.nbClients] = index;
                j++;
            }
        }

        // Run the individual through the split algorithm.
        split.generalSplit(&result, parent1.cost.nbRoutes);

        // Any decent compiler will implement return-value optimisation
        // (copy elision) and will move "result" at the caller site, thus
        // avoiding a copy.
        return result;
    }

    void Genetic::updateCustomerFrequencyMatrix(const Individual& solution) const {
        assert(params.vfreq);

        for(const auto& route : solution.routes) {
            for(auto i = 0u; i < route.size(); ++i) {
                for(auto j = i + 1; j < route.size(); ++j) {
                    (*params.vfreq)[route[i]][route[j]] += 1;
                    (*params.vfreq)[route[j]][route[i]] += 1;
                }
            }
        }
    }

    void Genetic::updateArcFrequencyMatrix(const Individual& solution) const {
        assert(params.afreq);

        for(const auto& route : solution.routes) {
            if(route.empty()) {
                continue;
            }

            for(auto i = 0u; i < route.size() - 1u; ++i) {
                assert(route[i] != 0);
                assert(route[i + 1] != 0);

                (*params.afreq)[route[i]][route[i + 1]] += 1;
            }
        }
    }

    void Genetic::updatePathFrequencyMatrix(const genvrp::Individual& solution) const {
        assert(params.pfreq);

        for(const auto& route : solution.routes) {
            if(route.empty()) {
                continue;
            }

            for(auto it = route.begin(); it <= route.end() - Params::record_path_size; ++it) {
                const auto path = std::vector<int>(it, it + Params::record_path_size);
                const auto trieIt = params.pfreq->find(path);

                if(trieIt != params.pfreq->end()) {
                    ++(trieIt->second);
                } else {
                    (*params.pfreq)[path] = 1u;
                }
            }
        }
    }
} // namespace genvrp