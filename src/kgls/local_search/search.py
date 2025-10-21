
import logging
import math
import time
from typing import Any

from .operator_relocation_chain import search_relocation_chains
from .operator_linkernighan import run_lin_kernighan_heuristic
from .operator_3_opt import search_3_opt_moves
from .operator_cross_exchange import search_cross_exchanges
from ..datastructure import Node, Route, VRPSolution, CostEvaluator


logger = logging.getLogger(__name__)

# TODO best or first improving move
# TODO execute operator until no better solution found?


def improve_route(
        route: Route,
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        run_parameters: dict[str, Any],
) -> None:
    start = time.time()

    if route.size > 2:
        run_lin_kernighan_heuristic(
            solution=solution,
            cost_evaluator=cost_evaluator,
            route=route,
            max_depth=run_parameters['depth_lin_kernighan']
        )
    end = time.time()
    solution.solution_stats['time_lin_kernighan'] += end - start


def get_disjunct_moves(moves: list) -> list:
    disjunct_moves = []
    for move in moves:
        is_disjunct = True
        for disjunct_move in disjunct_moves:
            if not move.is_disjunct(disjunct_move):
                is_disjunct = False
                break

        if is_disjunct:
            disjunct_moves.append(move)

    return disjunct_moves


def find_best_improving_moves(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        start_nodes: list[Node],
        intra_route_opt: bool,
        operator_name: str,
        run_parameters: dict[str, Any],
) -> tuple[int, set[Route]]:

    operators = {
        "relocation_chain": search_relocation_chains,
        "segment_move": search_3_opt_moves,
        "cross_exchange": search_cross_exchanges,
    }
    operator_parameters = {
        "relocation_chain": {"max_depth": run_parameters['depth_relocation_chain']},
        "segment_move": dict(),
        "cross_exchange": dict(),
    }

    if operator_name not in operators:
        raise ValueError(f"Operator '{operator_name}' is not defined")

    start = time.time()

    candidate_moves = operators[operator_name](
        solution=solution,
        cost_evaluator=cost_evaluator,
        start_nodes=start_nodes,
        **operator_parameters[operator_name])

    end = time.time()
    solution.solution_stats[f'time_{operator_name}'] += end - start

    if candidate_moves:
        # find all disjunct moves, sorted by steepest descent
        logger.debug(
            f'Found {len(candidate_moves)} improving moves, '
            f'current solution value: {cost_evaluator.get_solution_costs(solution)}'
        )
        changed_routes = set()
        disjunct_moves = get_disjunct_moves(candidate_moves)

        # execute the moves
        for move in disjunct_moves:
            changed_routes = changed_routes | move.get_routes()
            old_costs = cost_evaluator.get_solution_costs(solution)

            move.execute(solution)
            solution.solution_stats[f'move_count_{operator_name}'] += 1
            solution.plot(cost_evaluator.get_solution_costs(solution, True))

            # validate changes in solution
            new_costs = cost_evaluator.get_solution_costs(solution)
            improvement = old_costs - new_costs
            assert math.isclose(improvement, move.improvement), \
                f'Improvement of move {operator_name} was {improvement} ' \
                f'but expected was {move.improvement}'
            solution.validate()

        # optimize all changed routes
        if intra_route_opt:
            for route in changed_routes:
                improve_route(route, solution, cost_evaluator, run_parameters)

        return len(disjunct_moves), changed_routes

    else:
        return 0, set()


def local_search(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        start_from_nodes: set[Node],
        intra_route_opt: bool,
        run_parameters: dict[str, Any],
) -> tuple[int, set[Route]]:

    num_executed_moves = 0
    all_changed_routes = set()

    for move_type in run_parameters['moves']:
        found_moves, changed_routes = find_best_improving_moves(
            solution=solution,
            cost_evaluator=cost_evaluator,
            start_nodes=start_from_nodes,
            intra_route_opt=intra_route_opt,
            operator_name=move_type,
            run_parameters=run_parameters
        )
        num_executed_moves += found_moves
        all_changed_routes = all_changed_routes | changed_routes

    return num_executed_moves, all_changed_routes


def improve_solution(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        start_search_from_routes: set[Route],
        run_parameters: dict[str, Any],
) -> None:
    # intra-route optimization of routes
    for route in start_search_from_routes:
        improve_route(route, solution, cost_evaluator, run_parameters)

    # inter-route optimization, starting from all routes in 'start_search_from_routes'
    start_from_nodes = set()
    for route in start_search_from_routes:
        start_from_nodes.update(route.customers)
    changes_found = True

    while changes_found:
        executed_moves, _ = local_search(
            solution=solution,
            cost_evaluator=cost_evaluator,
            start_from_nodes=start_from_nodes,
            intra_route_opt=True,
            run_parameters=run_parameters
        )
        changes_found = executed_moves > 0


def perturbate_solution(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        run_parameters: dict[str, Any],
) -> set[Route]:
    logger.debug('Starting perturbation of solution')

    # add previous penalties to costs of edges and compute the badness of the edges of the current solution
    cost_evaluator.enable_penalization()
    cost_evaluator.determine_edge_badness(solution.routes)

    applied_changes: int = 0
    changed_routes_perturbation = set()

    while applied_changes < run_parameters['num_perturbations']:
        worst_edge = cost_evaluator.get_and_penalize_worst_edge()
        logger.debug(f'Penalizing edge({worst_edge.get_first_node()} - {worst_edge.get_second_node()})')
        start_from_nodes = [node for node in worst_edge.nodes if not node.is_depot]

        executed_moves, changed_routes = local_search(solution, cost_evaluator, start_from_nodes, False, run_parameters)

        applied_changes += executed_moves
        changed_routes_perturbation.update(changed_routes)

    cost_evaluator.disable_penalization()

    return changed_routes_perturbation
