import logging
import math
import time
from typing import Any, Optional

from .datastructure import CostEvaluator, VRPProblem, VRPSolution
from .read_write.problem_reader import read_vrp_instance
from .read_write.solution_reader import read_vrp_solution
from .local_search import improve_solution, perturbate_solution
from .solution_construction import clark_wright_route_reduction
from .abortion_condition import BaseAbortionCondition, MaxRuntimeCondition, MaxIterationsCondition, \
    RuntimeWithoutImprovementCondition, IterationsWithoutImprovementCondition

import os
import csv

logger = logging.getLogger(__name__)

DEFAULT_PARAMETERS = {
    'depth_lin_kernighan': 4,
    'depth_relocation_chain': 3,
    'num_perturbations': 3,
    'neighborhood_size': 20,
    'moves': ['segment_move', 'cross_exchange', 'relocation_chain']
}


class KGLS:
    _abortion_condition: BaseAbortionCondition
    _vrp_instance: VRPProblem
    _cost_evaluator: CostEvaluator
    _best_solution: Optional[VRPSolution]
    _cur_solution: Optional[VRPSolution]
    _iteration: int
    _best_solution_costs: int
    _best_iteration: int
    _best_solution_time: int
    _run_stats: list[dict[str, any]]

    def __init__(self, path_to_instance_file: str, record_path: str, **kwargs):
        self.run_parameters = self._get_run_parameters(**kwargs)
        self._vrp_instance = read_vrp_instance(path_to_instance_file)
        self._cost_evaluator = CostEvaluator(self._vrp_instance.nodes, self._vrp_instance.capacity, self.run_parameters)
        self._best_solution_costs = math.inf
        self._cur_solution = None
        self._best_solution = None
        self._abortion_condition = IterationsWithoutImprovementCondition(100)

        self.record_path = record_path
        self.nodes_number = len(self._vrp_instance.nodes)

    @staticmethod
    def _get_run_parameters(**kwargs) -> dict[str, Any]:
        # Check user-provided parameters
        for key, value in kwargs.items():
            if key not in DEFAULT_PARAMETERS:
                raise ValueError(
                    f'Invalid parameter: {key}. '
                    f'Parameter must be in {", ".join(DEFAULT_PARAMETERS.keys())}')

            if key != 'moves' and not isinstance(value, int):
                actual_type = type(value).__name__
                raise TypeError(f"Parameter '{key}' must be of type int, got {actual_type}")

            elif key == 'moves':
                if not isinstance(value, list):
                    actual_type = type(value).__name__
                    raise TypeError(f"Parameter '{key}' must be of type list, got {actual_type}")
                if any(move not in DEFAULT_PARAMETERS["moves"] for move in value):
                    raise ValueError(f'Moves must be in {", ".join(DEFAULT_PARAMETERS["moves"])}')

        # update default parameters
        params = {**DEFAULT_PARAMETERS, **kwargs}
        return params

    def best_solution_to_file(self, path_to_file: str):
        self._best_solution.to_file(path_to_file)

    def set_abortion_condition(self, condition_name: str, param: int):
        # Set the abortion condition for KGLS.
        condition_classes = {
            "max_iterations": MaxIterationsCondition,
            "max_runtime": MaxRuntimeCondition,
            "iterations_without_improvement": IterationsWithoutImprovementCondition,
            "runtime_without_improvement": RuntimeWithoutImprovementCondition,
        }
        if condition_name not in condition_classes:
            raise ValueError(
                f"Unknown abortion condition: {condition_name}. "
                f"Choose one of {' ,'.join(condition_classes.keys())}.")
        self._abortion_condition = condition_classes[condition_name](param)

    def _update_run_stats(self, start_time):
        current_costs = self._cost_evaluator.get_solution_costs(self._cur_solution)

        if self._vrp_instance.bks != float('inf'):
            solution_quality = 100 * (current_costs - self._vrp_instance.bks) / self._vrp_instance.bks
        else:
            solution_quality = current_costs

        # update stats if new best solution was found
        if current_costs < self._best_solution_costs:
            logger.info(
                f'{(time.time() - start_time): 1f} '
                f'{solution_quality: .2f}'
            )
            self._best_iteration = self._iteration
            self._best_solution_time = time.time()
            self._best_solution_costs = current_costs
            self._best_solution = self._cur_solution.copy()

            # 获取文件名（去掉路径部分）
            # 保存到CSV文件
            with open(self.record_path, 'a', newline='') as csvfile:
                writer = csv.writer(csvfile, delimiter=';')  # 设置分隔符为分号
                writer.writerow([f'{(time.time() - start_time):.2f}', current_costs])

        self._run_stats.append({
            "run_time": time.time() - start_time,
            "iteration": self._iteration,
            "costs": current_costs,
            "best_costs": self._best_solution_costs,
            "best_gap": None if self._vrp_instance.bks == float('inf') else solution_quality,
        })

    def run(self, visualize_progress: bool = False, start_solution: VRPSolution = None):
        logger.info(f'Running KGLS. {self._abortion_condition.msg}')

        start_time = time.time()
        self._run_stats = []
        self._iteration = 0

        # construct initial solution
        if start_solution is None:
            self._cur_solution = clark_wright_route_reduction(
                vrp_instance=self._vrp_instance,
                cost_evaluator=self._cost_evaluator
            )
        else:
            self._cur_solution = start_solution

        if visualize_progress:
            self._cur_solution.start_plotting()

        self._update_run_stats(start_time)

        improve_solution(
            solution=self._cur_solution,
            cost_evaluator=self._cost_evaluator,
            start_search_from_routes=self._cur_solution.routes,
            run_parameters=self.run_parameters,
        )
        self._update_run_stats(start_time)

        while not self._abortion_condition.should_abort(
                iteration=self._iteration,
                best_iteration=self._best_iteration,
                start_time=start_time,
                best_sol_time=self._best_solution_time
        ):
            self._iteration += 1

            changed_routes = perturbate_solution(
                solution=self._cur_solution,
                cost_evaluator=self._cost_evaluator,
                run_parameters=self.run_parameters,
            )
            improve_solution(
                solution=self._cur_solution,
                cost_evaluator=self._cost_evaluator,
                start_search_from_routes=changed_routes,
                run_parameters=self.run_parameters,
            )

            self._update_run_stats(start_time)

        logger.info(f'KGLS finished after {(time.time() - start_time): 1f} seconds and '
                    f'{self._iteration} iterations.')

    def print_time_distribution(self):
        time_entries = {
            k.replace("time_", ""): v
            for k, v in self._cur_solution.solution_stats.items()
            if k.startswith("time_")
        }

        # Print table header
        print(f"{'Move':<20}{'Time Percentage':<15}")
        print("-" * 35)

        # Print rows
        running_percentage = 0
        for key, run_time in time_entries.items():
            percentage = (run_time / self.total_runtime) * 100
            running_percentage += percentage
            print(f"{key:<20}{int(percentage):<15}")

        print(f"{'Other':<20}{int(100 - running_percentage):<15}%")

    @property
    def best_solution(self):
        return self._best_solution

    @property
    def best_found_solution_value(self) -> int:
        return self._best_solution_costs

    @property
    def best_found_gap(self) -> Optional[float]:
        if self._vrp_instance.bks != float('inf'):
            return 100 * (self._best_solution_costs - self._vrp_instance.bks) / self._vrp_instance.bks
        else:
            return None

    @property
    def total_runtime(self):
        return self._run_stats[-1]["run_time"]

    def _load_solution(self, path_to_file: str) -> VRPSolution:
        if self._cur_solution is not None:
            raise ValueError(
                'Cannot overwrite current solution with a new one. '
                'Please create a new KGLS instance to start from a solution.'
            )

        solution = read_vrp_solution(path_to_file, self._vrp_instance)
        return solution

    def start_from_solution(self, path_to_file: str, visualize_progress: bool = False):
        logger.info(f'Continuing KGLS from specified solution')

        logger.info(f'Loading starting solution')
        starting_solution = self._load_solution(path_to_file)

        self.run(visualize_progress=visualize_progress, start_solution=starting_solution)
