import heapq
from collections import defaultdict
from itertools import cycle
import math
from typing import Any

from .node import Node
from .edge import Edge
from .route import Route
from .vrp_solution import VRPSolution


class MaxHeapWithUpdate:
    def __init__(self, elements: list[Edge]):
        # Create a max-heap by inverting values (negate them)
        self.heap = elements
        heapq.heapify(self.heap)

    def get_max_element(self):
        # Pop the max element (the root of the heap)
        return heapq.heappop(self.heap)  # Removes the largest (smallest negative)

    def insert_element(self, element: Edge):
        # Add the new value (inverted for max-heap)
        heapq.heappush(self.heap, element)

    def get_sorted_list(self):
        # To get a sorted list, we retrieve and negate all elements
        return sorted([elem for elem in self.heap])


class CostEvaluator:

    def __init__(self, nodes: list[Node], capacity: int, run_parameters: dict[str, Any]):
        self._penalization_enabled: bool = False
        self._edge_penalties: dict[Edge, int] = defaultdict(int)
        self._baseline_cost: float = 0.0
        self._edge_ranking: MaxHeapWithUpdate = None
        self.neighborhood_size = run_parameters['neighborhood_size']
        self._capacity = capacity

        # compute costs as euclidean distance between each pair of nodes
        self._costs = dict()
        for node1 in nodes:
            self._costs[node1.node_id] = dict()
            for node2 in nodes:
                self._costs[node1.node_id][node2.node_id] = self._compute_euclidean_distance(node1, node2)

        # initialize penalized as euclidean costs
        self._penalized_costs = dict()
        for node1 in nodes:
            self._penalized_costs[node1.node_id] = dict()
            for node2 in nodes:
                self._penalized_costs[node1.node_id][node2.node_id] = self._costs[node1.node_id][node2.node_id]

        # get neighborhood for each node
        self._neighborhood = self._compute_neighborhood(nodes)

        self._baseline_cost = int(sum(
            self.get_distance(node, other)
            for node in nodes
            if not node.is_depot
            for other in self._neighborhood[node]
        ) / (self.neighborhood_size * len(nodes)))

        self._penalization_criterium_options = cycle(["width", "length", "width_length"])
        self._penalization_criterium = next(self._penalization_criterium_options)

    @staticmethod
    def _compute_euclidean_distance(node1: Node, node2: Node) -> int:
        return round(
            math.sqrt(
                math.pow(node1.x_coordinate - node2.x_coordinate, 2) +
                math.pow(node1.y_coordinate - node2.y_coordinate, 2)
            )
        )

    def get_neighborhood(self, node: Node) -> list[Node]:
        return self._neighborhood[node]

    def _compute_neighborhood(self, nodes: list[Node]) -> list[Node]:
        neighborhood = {
            node: self._get_nearest_neighbors(node, nodes)
            for node in nodes
            if not node.is_depot
        }

        return neighborhood

    def _get_nearest_neighbors(self, node: Node, nodes: list[Node]) -> list[Node]:
        # Sort nodes by their Euclidean distance to the given node, ascending
        sorted_nodes = sorted(
            nodes,
            key=lambda x: self._compute_euclidean_distance(x, node)
        )

        # Filter out the depot and the node itself
        nearest_neighbors = [
            n for n in sorted_nodes if not n.is_depot and n != node
        ]

        return nearest_neighbors[:self.neighborhood_size]

    def is_feasible(self, capacity: int) -> bool:
        return capacity <= self._capacity

    def determine_edge_badness(self, routes: list[Route]):
        edges_in_solution: list[Edge] = []

        criterium_functions = {
            "length": self._compute_edge_length_value,
            "width": self._compute_edge_width_value,
            "width_length": self._compute_edge_width_length_value
        }
        # Get the computation function based on the current penalization criterium
        compute_edge_value = criterium_functions[self._penalization_criterium]

        for route in routes:
            center_x, center_y = (None, None)
            if self._penalization_criterium in {"width", "width_length"}:
                center_x, center_y = self._compute_route_center(route.nodes)

            for edge in route.edges:
                # Compute the value for the edge
                edge.value = compute_edge_value(edge, center_x, center_y, route)
                edge.value /= (1 + self._edge_penalties[edge])
                edges_in_solution.append(edge)

        # Update edge ranking
        self._edge_ranking = MaxHeapWithUpdate(edges_in_solution)

        # Rotate to next penalization criterium
        self._penalization_criterium = next(self._penalization_criterium_options)

    def _compute_edge_length_value(self, edge: Edge, *args) -> float:
        return self._costs[edge.nodes[0].node_id][edge.nodes[1].node_id]

    def _compute_edge_width_value(self, edge: Edge, center_x: float, center_y: float, route: Route) -> float:
        return self._compute_edge_width(edge, center_x, center_y, route.depot)

    def _compute_edge_width_length_value(self, edge: Edge, center_x: float, center_y: float, route: Route) -> float:
        width_value = self._compute_edge_width(edge, center_x, center_y, route.depot)
        length_value = self._costs[edge.nodes[0].node_id][edge.nodes[1].node_id]
        return width_value + length_value

    def enable_penalization(self):
        self._penalization_enabled = True

    def disable_penalization(self):
        self._penalization_enabled = False

    def get_distance(self, node1: Node, node2: Node) -> int:
        if not self._penalization_enabled:
            return self._costs[node1.node_id][node2.node_id]  # node1.get_distance(node2)
        else:
            return self._penalized_costs[node1.node_id][node2.node_id] # node1.get_distance(node2) + 0.1 * self._baseline_cost * self._edge_penalties[Edge(node1, node2)]

    def get_and_penalize_worst_edge(self) -> Edge:
        worst_edge = self._edge_ranking.get_max_element()
        self._edge_penalties[worst_edge] += 1

        # update costs
        node1 = worst_edge.nodes[0].node_id
        node2 = worst_edge.nodes[1].node_id
        penalization_costs = round(
                self._costs[node1][node2]
                + 0.1 * self._baseline_cost * self._edge_penalties[worst_edge]
        )
        self._penalized_costs[node1][node2] = penalization_costs
        self._penalized_costs[node2][node1] = penalization_costs

        # update (reduce) 'badness' of the just penalized edge (to avoid penalizing it again too soon)
        worst_edge.value = (
                self._costs[node1][node2]/
                (1 + self._edge_penalties[worst_edge])
        )
        self._edge_ranking.insert_element(worst_edge)

        return worst_edge

    def penalize(self, edge: Edge) -> None:
        self._edge_penalties[edge] += 1

    def get_solution_costs(self, solution: VRPSolution, ignore_penalties: bool = False) -> int:
        solution_costs: int = 0

        for route in solution.routes:
            if route.size > 0:
                for idx in range(len(route._nodes) - 1):
                    edge_node1 = route._nodes[idx]
                    edge_node2 = route._nodes[idx + 1]

                    if ignore_penalties:
                        solution_costs += self._costs[edge_node1.node_id][edge_node2.node_id]
                    else:
                        solution_costs += self.get_distance(edge_node1, edge_node2)

        return solution_costs

    @staticmethod
    def _compute_edge_width(
            edge: Edge,
            route_center_x: float,
            route_center_y: float,
            depot: Node
    ) -> float:
        node1 = edge.get_first_node()
        node2 = edge.get_second_node()

        distance_depot_center = (
            math.sqrt(
                math.pow(depot.x_coordinate - route_center_x, 2) +
                math.pow(depot.y_coordinate - route_center_y, 2)
            )
        )

        distance_node1 = (
                (route_center_y - depot.y_coordinate) * node1.x_coordinate
                - (route_center_x - depot.x_coordinate) * node1.y_coordinate
                + (route_center_x * depot.y_coordinate) - (route_center_y * depot.x_coordinate)
        )
        distance_node1 = 0 if distance_depot_center == 0 else distance_node1 / distance_depot_center

        distance_node2 = (
                (route_center_y - depot.y_coordinate) * node2.x_coordinate
                - (route_center_x - depot.x_coordinate) * node2.y_coordinate
                + (route_center_x * depot.y_coordinate) - (route_center_y * depot.x_coordinate)
        )
        distance_node2 = 0 if distance_depot_center == 0 else distance_node2 / distance_depot_center

        return abs(distance_node1 - distance_node2)

    @staticmethod
    def _compute_route_center(nodes: list[Node]) -> tuple[float, float]:
        mean_x = sum(node.x_coordinate for node in nodes) / len(nodes)
        mean_y = sum(node.y_coordinate for node in nodes) / len(nodes)

        return mean_x, mean_y

