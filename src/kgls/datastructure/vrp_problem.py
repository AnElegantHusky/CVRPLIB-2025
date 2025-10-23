
from typing import List

from .node import Node


class VRPProblem:
    # TODO make immutable
    nodes: List[Node]
    capacity: int
    bks: float

    def __init__(self, nodes: List[Node], capacity: int, bks: float = float('inf')):
        self.nodes: List[nodes] = nodes
        self.capacity: int = capacity
        self.bks: float = bks

        self.customers = [node for node in nodes if not node.is_depot]
        self.depot = [node for node in nodes if node.is_depot][0]
