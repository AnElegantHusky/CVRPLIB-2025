from dataclasses import dataclass


@dataclass(frozen=True)
class Node:
    node_id: int
    x_coordinate: float
    y_coordinate: float
    demand: int
    is_depot: bool

    def __repr__(self):
        return str(self.node_id)

    def __lt__(self, other):
        return self.node_id > other.node_id

    def __eq__(self, other):
        return self.node_id == other.node_id

    def __hash__(self):
        return self.node_id
