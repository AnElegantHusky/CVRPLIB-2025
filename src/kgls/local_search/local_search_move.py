from abc import ABC, abstractmethod

from ..datastructure import Route, VRPSolution


class LocalSearchMove(ABC):
    improvement: int

    def __init__(self):
        pass

    @abstractmethod
    def execute(self, solution: VRPSolution):
        pass

    @abstractmethod
    def get_routes(self) -> list[Route]:
        pass

    @abstractmethod
    def is_disjunct(self, other):
        pass

    def __lt__(self, other):
        return self.improvement > other.improvement

