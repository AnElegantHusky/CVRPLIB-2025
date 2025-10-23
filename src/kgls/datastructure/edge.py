from .node import Node


def get_sorted_tuple(node1: Node, node2: Node):
    if node1.node_id >= node2.node_id:
        return node1, node2
    else:
        return node2, node1


class Edge:
    def __init__(self, node1: Node, node2: Node, value: int = 0):
        self.value = value
        self.nodes = get_sorted_tuple(node1, node2)

    def __eq__(self, other):
        if not isinstance(other, Edge):
            return NotImplemented
        return self.get_first_node() == other.get_first_node() and self.get_second_node() == other.get_second_node()

    def __hash__(self):
        return hash(self.nodes)

    def __repr__(self):
        return f"Edge({self.nodes[0]}, {self.nodes[1]})"

    def has_depot(self) -> bool:
        return self.nodes[0].is_depot or self.nodes[1].is_depot

    def get_first_node(self) -> Node:
        return self.nodes[0]

    def get_second_node(self) -> Node:
        return self.nodes[1]

    def contains(self, node: Node) -> bool:
        """Check if the given node is part of the edge."""
        return node in self.nodes

    def other_node(self, node):
        """Return the other node of the edge if the given node is part of it."""
        if node not in self.nodes:
            return None

        return self.nodes[0] if node == self.nodes[1] else self.nodes[1]

    def __lt__(self, other):
        return self.value > other.value