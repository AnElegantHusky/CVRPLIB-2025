import logging

from ..datastructure import Node, Route, VRPSolution, CostEvaluator
from .local_search_move import LocalSearchMove

logger = logging.getLogger(__name__)


class SegmentMove(LocalSearchMove):

    def __init__(
            self,
            segment: list[Node],
            from_route: Route,
            to_route: Route,
            move_after: Node,
            improvement: float
    ):
        self.segment: list[Node] = segment
        self.from_route = from_route
        self.to_route = to_route
        self.move_after: Node = move_after
        self.improvement: float = improvement

    def get_routes(self) -> set[Route]:
        return set([self.from_route, self.to_route])

    def is_disjunct(self, other):
        if self.from_route in other.get_routes():
            return False
        if self.to_route in other.get_routes():
            return False

        return True

    def execute(self, solution: VRPSolution):
        logger.debug(f'Executing Segment relocation with segment of size {len(self.segment)} '
                     f'with improvement of {int(self.improvement)}')

        solution.remove_nodes(self.segment)
        solution.insert_nodes_after(self.segment, self.move_after, self.to_route)


def search_3_opt_moves_from(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        start_node: Node,
        segment_directions: list[int] = [0, 1],
        insert_directions: list[int] = [0, 1]
) -> list[SegmentMove]:
    candidate_moves: list[SegmentMove] = []
    from_route = solution.route_of(start_node)

    for segment_direction in segment_directions:
        for insert_direction in insert_directions:

            #segment_1_prev = start_node.get_neighbour(1 - segment_direction)
            segment_1_prev = solution.neighbour(start_node, 1 - segment_direction)

            for insert_next_to in cost_evaluator.get_neighborhood(start_node):
                to_route = solution.route_of(insert_next_to)

                if to_route != from_route:
                    # compute improvement of first edge change
                    #insert_next_to_2 = insert_next_to.get_neighbour(insert_direction)
                    insert_next_to_2 = solution.neighbour(insert_next_to, insert_direction)

                    move_start_improvement = (
                        cost_evaluator.get_distance(start_node, segment_1_prev)
                        + cost_evaluator.get_distance(insert_next_to, insert_next_to_2)
                        - cost_evaluator.get_distance(insert_next_to, start_node)
                    )

                    if move_start_improvement > 0:
                        segment_end = start_node
                        segment_list = [segment_end]
                        route_2_new_volume = to_route.volume + segment_end.demand

                        while not segment_end.is_depot and cost_evaluator.is_feasible(route_2_new_volume):
                            #segment_disconnect_2 = segment_end.get_neighbour(segment_direction)
                            segment_disconnect_2 = solution.neighbour(segment_end, segment_direction)

                            move_end_improvement = (
                                    cost_evaluator.get_distance(segment_end, segment_disconnect_2)
                                    - cost_evaluator.get_distance(segment_1_prev, segment_disconnect_2)
                                    - cost_evaluator.get_distance(segment_end, insert_next_to_2)
                            )

                            improvement = move_start_improvement + move_end_improvement
                            if improvement > 0:
                                # store move
                                if insert_direction == 1:
                                    insert_after = insert_next_to
                                else:
                                    insert_after = insert_next_to_2

                                candidate_moves.append(
                                    SegmentMove(
                                        segment=segment_list.copy(),
                                        from_route=from_route,
                                        to_route=to_route,
                                        move_after=insert_after,
                                        improvement=improvement
                                    )
                                )

                            # extend
                            segment_end = segment_disconnect_2
                            if insert_direction == 1:
                                segment_list.append(segment_end)
                            else:
                                segment_list.insert(0, segment_end)
                            route_2_new_volume += segment_end.demand

    return candidate_moves


def search_3_opt_moves(
        solution: VRPSolution,
        cost_evaluator: CostEvaluator,
        start_nodes: list[Node],
) -> list[SegmentMove]:
    candidate_moves = []
    for start_node in start_nodes:
        candidate_moves.extend(
            search_3_opt_moves_from(solution, cost_evaluator, start_node)
        )

    return sorted(candidate_moves)


