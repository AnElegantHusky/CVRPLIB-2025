from typing import List

from .edge import Edge
from .node import Node


class Route:
    def __init__(self, nodes: List[Node], route_index: int):
        # Initialize the route with the depot as both the first and last node.
        assert nodes[0].is_depot, 'First node of a route has to be a depot.'
        assert nodes[-1].is_depot, 'Last node of a route has to be a depot.'
        assert nodes[0] == nodes[-1], 'Start and return depot has to be the same'

        self.route_index = route_index
        self.depot: Node = nodes[0]
        self._nodes: list = nodes.copy()

        self.size = len(nodes) - 2  # Number of customers (not including depot)
        self.volume = sum(node.demand for node in self._nodes)  # Sum of demand of all customers of the route

        self.validate()

    def __repr__(self):
        return '-'.join([str(node.node_id) for node in self._nodes])

    def __hash__(self):
        return hash(self.route_index)

    def __eq__(self, other):
        return self.route_index == other.route_index

    def remove_customer(self, node: Node):
        assert node.is_depot is False, 'A depot is removed from a route'
        assert node in self._nodes, 'Node does not exist in route'
        self.size -= 1
        self.volume -= node.demand
        self._nodes.remove(node)

    def add_customers_after(self, nodes_to_add: list[Node], insert_after: Node):
        if insert_after not in self._nodes:
            raise ValueError(f"Customer {insert_after} not found in the route.")

        index = self._nodes.index(insert_after)
        self._nodes = self._nodes[:index + 1] + nodes_to_add + self._nodes[index + 1:]

        for node in nodes_to_add:
            assert node.is_depot is False, 'A depot is inserted into a route'
            self.size += 1
            self.volume += node.demand

    @property
    def customers(self) -> list[Node]:
        return self._nodes[1:-1]

    @property
    def nodes(self) -> list[Node]:
        return self._nodes[1:]

    @property
    def nodes_without_depot(self) -> list[Node]:
        return self._nodes[1:-1]

    @property
    def edges(self) -> list[Edge]:
        return [
            Edge(self._nodes[idx], self._nodes[idx + 1])
            for idx in range(len(self._nodes) - 1)
        ]

    def validate(self):
        assert self._nodes[0].is_depot, 'First node has to be a depot.'
        assert self._nodes[-1].is_depot, 'Last node has to be a depot.'
        assert self._nodes[0] == self._nodes[-1], 'Start and return depot have to be the same'
        assert self.size == len(self._nodes) - 2
        assert self.volume == sum(node.demand for node in self._nodes)

        for node in self._nodes[1:-1]:
            assert node.is_depot == False

    def print(self) -> str:
        return '-'.join([str(node.node_id) for node in self._nodes])
